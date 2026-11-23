package main

import "testing"

func TestResolveEnvironmentAliases(t *testing.T) {
	tests := []struct {
		name              string
		canonical         string
		canonicalSet      bool
		legacy            string
		legacySet         bool
		fallback          string
		want              string
		wantConflictError bool
	}{
		{name: "canonical only", canonical: "new", canonicalSet: true, fallback: "default", want: "new"},
		{name: "legacy only", legacy: "old", legacySet: true, fallback: "default", want: "old"},
		{name: "equal aliases", canonical: "same", canonicalSet: true, legacy: "same", legacySet: true, want: "same"},
		{name: "different aliases fail closed", canonical: "new", canonicalSet: true, legacy: "old", legacySet: true, wantConflictError: true},
		{name: "fallback", fallback: "default", want: "default"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got, err := resolveEnvironmentAliasValues(test.canonical, test.canonicalSet, test.legacy, test.legacySet, test.fallback)
			if (err != nil) != test.wantConflictError {
				t.Fatalf("conflict error=%v, want %v", err, test.wantConflictError)
			}
			if err == nil && got != test.want {
				t.Fatalf("value=%q, want %q", got, test.want)
			}
		})
	}
}
