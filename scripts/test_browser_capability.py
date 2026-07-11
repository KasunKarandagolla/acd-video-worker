#!/usr/bin/env python3
"""
Test Hermes browser capability on current environment.
Tests: backend availability, YouTube search, clean shutdown.
Outputs: BROWSER_SUPPORTED | BROWSER_PARTIALLY_SUPPORTED | BROWSER_UNSUPPORTED
"""

import os
import sys
import subprocess
import json
import tempfile
from pathlib import Path

def run_cmd(cmd, cwd=None, env=None, timeout=120):
    try:
        result = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "TIMEOUT"
    except Exception as e:
        return False, "", str(e)

def test_agent_browser_install():
    """Test if agent-browser can be installed and run."""
    print("Testing agent-browser (local backend)...")
    
    # Check if npx is available
    ok, _, _ = run_cmd(["npx", "--version"])
    if not ok:
        return False, "npx not available"
    
    # Try to run agent-browser install (dry-run/check)
    ok, out, err = run_cmd(["npx", "agent-browser", "--version"], timeout=60)
    if ok:
        print(f"  ✓ agent-browser available: {out.strip()}")
        return True, out.strip()
    else:
        print(f"  ⚠️  agent-browser not installed: {err[:200]}")
        # Try install
        ok, out, err = run_cmd(["npx", "agent-browser", "install"], timeout=180)
        if ok:
            print("  ✓ agent-browser installed successfully")
            return True, "installed"
        else:
            print(f"  ❌ agent-browser install failed: {err[:500]}")
            return False, err[:500]

def test_camofox():
    """Test if Camofox is available."""
    print("Testing Camofox...")
    camofox_url = os.environ.get("CAMOFOX_URL")
    if camofox_url:
        print(f"  CAMOFOX_URL set: {camofox_url}")
        # Could test connection here
        return True, "CAMOFOX_URL configured"
    else:
        print("  CAMOFOX_URL not set")
        return False, "CAMOFOX_URL not set"

def test_browser_tool_via_hermes():
    """Test browser tool via Hermes CLI."""
    print("Testing browser tool via Hermes...")
    
    hermes_home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
    profile_dir = Path(hermes_home) / "profiles" / "football-emotion"
    
    if not profile_dir.exists():
        return False, "football-emotion profile not found"
    
    env = os.environ.copy()
    env["HERMES_HOME"] = str(profile_dir)
    
    # Test with a simple navigation to a public page
    test_prompt = "Use the browser tool to open https://example.com and extract the page title. Return only the title."
    
    ok, out, err = run_cmd([
        "hermes", "-p", "football-emotion", "chat", "-q", test_prompt
    ], env=env, timeout=180)
    
    if ok:
        print(f"  ✓ Browser tool responded: {out[:200]}")
        return True, "browser_tool_worked"
    else:
        print(f"  ❌ Browser tool failed: {err[:500]}")
        return False, err[:500]

def test_youtube_search():
    """Test YouTube search via browser tool."""
    print("Testing YouTube search via browser...")
    
    hermes_home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
    profile_dir = Path(hermes_home) / "profiles" / "football-emotion"
    
    if not profile_dir.exists():
        return False, "profile not found"
    
    env = os.environ.copy()
    env["HERMES_HOME"] = str(profile_dir)
    
    test_prompt = (
        "Use the browser tool to go to YouTube search results for 'Messi World Cup 2022 final'. "
        "Extract the first 3 video titles and URLs. Return as JSON list."
    )
    
    ok, out, err = run_cmd([
        "hermes", "-p", "football-emotion", "chat", "-q", test_prompt
    ], env=env, timeout=180)
    
    if ok:
        print(f"  ✓ YouTube search responded: {out[:300]}")
        return True, "youtube_search_worked"
    else:
        print(f"  ❌ YouTube search failed: {err[:500]}")
        return False, err[:500]

def main():
    print("=" * 60)
    print("HERMES BROWSER CAPABILITY TEST")
    print("=" * 60)
    
    results = {}
    
    # Test 1: Local backend (agent-browser)
    ok, msg = test_agent_browser_install()
    results["agent_browser"] = {"supported": ok, "details": msg}
    
    # Test 2: Camofox
    ok, msg = test_camofox()
    results["camofox"] = {"supported": ok, "details": msg}
    
    # Test 3: Full browser tool via Hermes (only if profile exists)
    profile_exists = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser().joinpath("profiles/football-emotion").exists()
    if profile_exists:
        ok, msg = test_browser_tool_via_hermes()
        results["browser_tool"] = {"supported": ok, "details": msg}
        
        if ok:
            ok, msg = test_youtube_search()
            results["youtube_search"] = {"supported": ok, "details": msg}
    else:
        results["browser_tool"] = {"supported": False, "details": "profile not found"}
        results["youtube_search"] = {"supported": False, "details": "profile not found"}
    
    # Determine overall verdict
    print("\n" + "=" * 60)
    print("VERDICT")
    print("=" * 60)
    
    # Check if any backend works
    any_backend = results["agent_browser"]["supported"] or results["camofox"]["supported"]
    browser_tool_works = results.get("browser_tool", {}).get("supported", False)
    youtube_works = results.get("youtube_search", {}).get("supported", False)
    
    if browser_tool_works and youtube_works:
        verdict = "BROWSER_SUPPORTED"
    elif browser_tool_works or any_backend:
        verdict = "BROWSER_PARTIALLY_SUPPORTED"
    else:
        verdict = "BROWSER_UNSUPPORTED"
    
    print(f"Result: {verdict}")
    print(json.dumps(results, indent=2))
    
    # Write result file for validation script
    with open("/tmp/browser_capability_result.json", "w") as f:
        json.dump({"verdict": verdict, "details": results}, f)
    
    return 0 if verdict != "BROWSER_UNSUPPORTED" else 1

if __name__ == "__main__":
    sys.exit(main())