# Installation & Setup Guide

Cord runs on Linux, macOS, and Windows with Python 3.10 or higher.

## Prerequisites

- **Python:** Version 3.10 or newer. Check your installed version:
  ```bash
  python3 --version
  ```
- **Git:** Required to clone the repository.
- **Discord Bot Token:** Required to run bots live on Discord. Obtain one from the [Discord Developer Portal](https://discord.com/developers/applications).

---

## 1. Installation

### Method A: Clone & Local Pip Install (Recommended)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/mannansainicyber-dev/cord-lang.git
   cd cord-lang
   ```

2. **(Optional) Create and activate a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install the package and CLI in editable mode:**
   ```bash
   pip install -e .
   ```

### Method B: Install Directly from Git URL

```bash
pip install git+https://github.com/mannansainicyber-dev/cord-lang.git
```

4. **Verify the installation:**
   ```bash
   cord --version
   ```
   Output should resemble:
   ```text
   Cord 0.2.0 (Python 3.12+)
   ```

---

## 2. Platform-Specific Notes

### Linux (Ubuntu / Debian / Fedora / Arch)
Ensure `python3-pip` and `python3-venv` are installed. If installing to the user directory without a virtual environment, ensure `~/.local/bin` is in your `PATH`:
```bash
export PATH="$HOME/.local/bin:$PATH"
```

### macOS
Install Python via Homebrew or official installers:
```bash
brew install python
```
Ensure Homebrew's bin directory is in your `PATH`.

### Windows
Ensure that during the Python installation from python.org, the **"Add Python to PATH"** checkbox is selected. You can run `cord` directly from PowerShell or Command Prompt.

---

## 3. Verifying Installation with Test Suite

Cord comes with an extensive, token-free test suite:
```bash
pytest
```
All tests should pass without needing an internet connection.
