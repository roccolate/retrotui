
import subprocess

targets = [
    "git:https://github.com",
    "LegacyGeneric:target=git:https://github.com",
    "gh:github.com:roccolate", 
    "LegacyGeneric:target=gh:github.com:roccolate",
    "danalopezarq-crypto",
    "LegacyGeneric:target=danalopezarq-crypto",
    "LegacyGeneric:target=GitHub for Visual Studio - https://roccolate@github.com/"
]

print("--- Clearing GitHub Credentials ---")
for t in targets:
    # Use full path to cmdkey just in case, but usually on path
    cmd = f'cmdkey /delete:"{t}"'
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True)

print("\n--- Rejecting via git credential system ---")
try:
    # This instructs Git's helper to forget the credential
    subprocess.run(["git", "credential", "reject"], input="protocol=https\nhost=github.com\n\n", text=True)
    print("Rejection command sent.")
except Exception as e:
    print(f"Git reject error: {e}")

print("\n--- Verification (Should show nothing for github) ---")
subprocess.run('cmdkey /list | findstr "github"', shell=True)
print("\nDone.")
