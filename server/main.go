package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"
)

func main() {
	_ = envAlias("HARDWARESTATUS_DEPLOYMENT_ENV", "HERMESSTATUS_DEPLOYMENT_ENV", "")
	var opts Options
	var legacyBind string
	var legacyPort int
	var printVersion bool
	var validateDeviceConfig bool

	flag.StringVar(&opts.ConfigPath, "config", envAlias("HARDWARESTATUS_CONFIG_PATH", "CONFIG_PATH", defaultConfigPath()), "configuration file")
	flag.StringVar(&opts.ConfigPath, "c", envAlias("HARDWARESTATUS_CONFIG_PATH", "CONFIG_PATH", defaultConfigPath()), "configuration file (shorthand)")
	flag.StringVar(&opts.StatsPath, "stats", envAlias("HARDWARESTATUS_STATS_PATH", "STATS_PATH", ""), "persistent stats JSON file")
	flag.StringVar(&opts.PersistencePath, "state", envAlias("HARDWARESTATUS_PERSISTENCE_PATH", "PERSISTENCE_PATH", ""), "multi-device state persistence file")
	flag.StringVar(&opts.RegistryPath, "device-registry", envAlias("HARDWARESTATUS_DEVICE_REGISTRY_PATH", "DEVICE_REGISTRY_PATH", ""), "read-only device registry")
	flag.StringVar(&opts.LegacyMappingPath, "legacy-device-mapping", envAlias("HARDWARESTATUS_LEGACY_DEVICE_MAPPING_PATH", "LEGACY_DEVICE_MAPPING_PATH", ""), "read-only legacy username mapping")
	flag.StringVar(&opts.DeviceCredentialsDir, "device-credentials", envAlias("HARDWARESTATUS_DEVICE_CREDENTIALS_DIR", "HERMESSTATUS_DEVICE_CREDENTIALS_DIR", ""), "read-only device credential directory")
	flag.BoolVar(&opts.DeviceEndpointEnabled, "device-endpoint", envBoolAlias("HARDWARESTATUS_DEVICE_ENDPOINT_ENABLED", "HERMESSTATUS_DEVICE_ENDPOINT_ENABLED", false), "enable the authenticated device update endpoint")
	flag.BoolVar(&opts.TrustedProxyMode, "device-trusted-proxy", envBoolAlias("HARDWARESTATUS_DEVICE_TRUSTED_PROXY", "HERMESSTATUS_DEVICE_TRUSTED_PROXY", false), "trust HTTPS forwarding only from explicit proxy addresses")
	flag.StringVar(&opts.TrustedProxyCIDRs, "device-trusted-proxy-cidrs", envAlias("HARDWARESTATUS_DEVICE_TRUSTED_PROXY_CIDRS", "HERMESSTATUS_DEVICE_TRUSTED_PROXY_CIDRS", ""), "comma-separated trusted proxy addresses or CIDRs")
	flag.StringVar(&opts.WebDir, "web-dir", envAlias("HARDWARESTATUS_WEB_DIR", "WEB_DIR", defaultWebDir()), "WebUI directory")
	flag.StringVar(&opts.WebDir, "d", envAlias("HARDWARESTATUS_WEB_DIR", "WEB_DIR", defaultWebDir()), "WebUI directory (shorthand)")
	flag.StringVar(&opts.HTTPAddr, "http", envAlias("HARDWARESTATUS_HTTP_ADDR", "HTTP_ADDR", defaultHTTPAddr()), "HTTP listen address")
	flag.StringVar(&opts.AgentAddr, "agent", envAlias("HARDWARESTATUS_AGENT_ADDR", "AGENT_ADDR", ":35601"), "agent TCP listen address")
	flag.StringVar(&legacyBind, "bind", "", "agent bind address (legacy compatibility)")
	flag.StringVar(&legacyBind, "b", "", "agent bind address (legacy shorthand)")
	flag.IntVar(&legacyPort, "port", 0, "agent TCP port (legacy compatibility)")
	flag.IntVar(&legacyPort, "p", 0, "agent TCP port (legacy shorthand)")
	flag.BoolVar(&opts.Verbose, "verbose", envBoolAlias("HARDWARESTATUS_VERBOSE", "VERBOSE", false), "verbose HTTP logging")
	flag.BoolVar(&opts.Verbose, "v", envBoolAlias("HARDWARESTATUS_VERBOSE", "VERBOSE", false), "verbose HTTP logging (shorthand)")
	flag.BoolVar(&printVersion, "version", false, "print version and exit")
	flag.BoolVar(&validateDeviceConfig, "validate-device-config", false, "validate read-only multi-device configuration and exit")
	flag.Parse()

	if printVersion {
		fmt.Printf("hardwarestatus-server %s commit=%s built=%s\n", version, commit, buildTime)
		return
	}
	if validateDeviceConfig {
		if exitCode := runDeviceConfigValidation(
			opts,
			os.Stdout,
			os.Stderr,
			time.Now(),
		); exitCode != 0 {
			os.Exit(exitCode)
		}
		return
	}
	if opts.StatsPath == "" {
		opts.StatsPath = filepath.Join(opts.WebDir, "json", "stats.json")
	}
	var pathErr error
	opts, pathErr = resolveOptionsPaths(opts)
	if pathErr != nil {
		fatalf("runtime path is invalid")
	}
	if legacyPort != 0 || legacyBind != "" {
		if legacyPort == 0 {
			legacyPort = 35601
		}
		opts.AgentAddr = net.JoinHostPort(legacyBind, strconv.Itoa(legacyPort))
	}
	opts.AdminToken = envAlias("HARDWARESTATUS_ADMIN_TOKEN", "ADMIN_TOKEN", "")
	opts.CORSOrigin = envAlias("HARDWARESTATUS_ADMIN_CORS_ORIGIN", "ADMIN_CORS_ORIGIN", "")

	if err := os.MkdirAll(filepath.Dir(opts.StatsPath), 0o755); err != nil {
		fatalf("create stats directory: %v", err)
	}
	app, err := NewApp(opts)
	if err != nil {
		fatalf("start: %v", err)
	}
	app.StartBackground()

	httpServer := app.HTTPServer()
	agentServer := NewAgentServer(app)
	errorsChannel := make(chan error, 2)
	go func() {
		app.logger.Printf("HTTP listening on %s", opts.HTTPAddr)
		if err := httpServer.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			errorsChannel <- fmt.Errorf("HTTP server: %w", err)
		}
	}()
	go func() {
		if err := agentServer.ListenAndServe(); err != nil {
			errorsChannel <- fmt.Errorf("agent server: %w", err)
		}
	}()

	reloadSignals := make(chan os.Signal, 1)
	stopSignals := make(chan os.Signal, 1)
	signal.Notify(reloadSignals, syscall.SIGHUP)
	signal.Notify(stopSignals, syscall.SIGINT, syscall.SIGTERM, syscall.SIGQUIT)
	defer signal.Stop(reloadSignals)
	defer signal.Stop(stopSignals)

	go func() {
		for range reloadSignals {
			if apiErr := app.ReloadConfig(); apiErr != nil {
				app.logger.Printf("reload config: %s", apiErr.Message)
				continue
			}
			app.logger.Printf("configuration reloaded; generation=%d", app.generation.Load())
		}
	}()

	var fatalErr error
	select {
	case signalValue := <-stopSignals:
		app.logger.Printf("received %s; shutting down", signalValue)
	case fatalErr = <-errorsChannel:
		app.logger.Printf("fatal: %v", fatalErr)
	}
	app.cancel()
	shutdownContext, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	_ = httpServer.Shutdown(shutdownContext)
	cancel()
	app.Close()
	if fatalErr != nil {
		os.Exit(1)
	}
}

func envOr(name, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(name)); value != "" {
		return value
	}
	return fallback
}

func envAlias(canonical, legacy, fallback string) string {
	canonicalValue, canonicalSet := os.LookupEnv(canonical)
	legacyValue, legacySet := os.LookupEnv(legacy)
	value, err := resolveEnvironmentAliasValues(
		canonicalValue, canonicalSet, legacyValue, legacySet, fallback,
	)
	if err != nil {
		fatalf("conflicting canonical and legacy environment aliases: %s", canonical)
	}
	return value
}

func envBoolAlias(canonical, legacy string, fallback bool) bool {
	value := envAlias(canonical, legacy, "")
	if value == "" {
		return fallback
	}
	parsed, err := strconv.ParseBool(value)
	if err != nil {
		fatalf("invalid boolean environment value: %s", canonical)
	}
	return parsed
}

func defaultConfigPath() string {
	if _, err := os.Stat("/app/config/config.json"); err == nil {
		return "/app/config/config.json"
	}
	return "config.json"
}

func defaultWebDir() string {
	if info, err := os.Stat("/app/web"); err == nil && info.IsDir() {
		return "/app/web"
	}
	return "../web"
}

func defaultHTTPAddr() string {
	if info, err := os.Stat("/app/web"); err == nil && info.IsDir() {
		return ":80"
	}
	return ":8080"
}

func envBool(name string, fallback bool) bool {
	value := strings.TrimSpace(os.Getenv(name))
	if value == "" {
		return fallback
	}
	parsed, err := strconv.ParseBool(value)
	if err != nil {
		return fallback
	}
	return parsed
}

func fatalf(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "hardwarestatus-server: "+format+"\n", args...)
	os.Exit(1)
}
