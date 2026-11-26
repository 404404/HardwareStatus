package main

import (
	"errors"
	"strings"
)

var errConflictingEnvironmentAliases = errors.New("conflicting environment aliases")

func resolveEnvironmentAliasValues(canonical string, canonicalSet bool, legacy string, legacySet bool, fallback string) (string, error) {
	canonical = strings.TrimSpace(canonical)
	legacy = strings.TrimSpace(legacy)
	if canonicalSet && legacySet && canonical != legacy {
		return "", errConflictingEnvironmentAliases
	}
	if canonicalSet {
		return canonical, nil
	}
	if legacySet {
		return legacy, nil
	}
	return fallback, nil
}
