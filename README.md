# 🛡️ VaultKey – Python Desktop Password Manager

A fully-featured, **native desktop** password manager built with Python 3,
PySide6, Firebase Authentication, Google Firestore, and AES-256 encryption.

---

## ✨ Features

| Feature | Details |
|---|---|
| **Authentication** | Email/password register & login, Google OAuth, password reset |
| **Master PIN** | bcrypt-hashed 4–6 digit PIN required to unlock the vault |
| **Vault** | Add, edit, delete, search passwords; copy to clipboard |
| **AES-256-GCM** | Every password field is encrypted before leaving the device |
| **Password Generator** | Configurable length, charset, copy-to-clipboard, strength meter |
| **Import / Export** | Encrypted JSON backup with PBKDF2-derived key |
| **Inactivity Lock** | Vault auto-locks after 5 minutes of inactivity |
| **Dark UI** | Polished dark theme with sidebar navigation and toast notifications |

---

## 📁 Project Structure

```
passwordmanager/
├── main.py                          ← Entry point
├── requirements.txt
├── .env.example
├── assets/
│   └── icon.png                     ← (optional) app icon
└── app/
    ├── ui/
    │   ├── login_window.py
    │   ├── register_window.py
    │   ├── vault_window.py          ← Main window + VaultPage + SettingsPage
    │   ├── pin_dialog.py            ← SetupPinDialog + UnlockPinDialog
    │   ├── add_password_dialog.py
    │   └── password_generator_widget.py
    ├── components/
    │   ├── password_card.py
    │   ├── sidebar.py
    │   ├── toast.py
    │   └── strength_meter.py
    ├── services/
    │   ├── firebase_service.py      ← Firebase Auth + Firestore REST API
    │   └── encryption_service.py   ← AES-256-GCM + bcrypt
    └── utils/
        ├── session.py               ← In-memory session state
        └── helpers.py               ← Password generator, strength scorer
```

---

## ⚙️ Prerequisites

- **Python 3.11+**
- A **Firebase project** (free Spark plan is sufficient)
- (Optional) A **Google Cloud OAuth 2.0 Desktop app credential** for Google login

---

## 🔥 Firebase Setup

### 1. Create a Firebase Project

1. Go to [https://console.firebase.google.com](https://console.firebase.google.com)
2. Click **Add project** and follow the wizard.

### 2. Enable Authentication

1. In your project, go to **Build → Authentication → Get started**.
2. Enable the **Email/Password** sign-in provider.
3. Enable the **Google** sign-in provider (set your support email).

### 3. Enable Cloud Firestore

1. Go to **Build → Firestore Database → Create database**.
2. Choose **Start in test mode** (you can tighten rules later).
3. Select a region close to your users.

### 4. Retrieve your Web API Key

1. Go to **Project Settings** (gear icon) → **General**.
2. Scroll to **Your apps** → add a **Web app** (just for the config values).
3. Copy `apiKey` → this is your `FIREBASE_API_KEY`.
4. Note the **Project ID** → this is your `FIREBASE_PROJECT_ID`.

### Firestore Security Rules (recommended)

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
      match /vault/{entryId} {
        allow read, write: if request.auth != null && request.auth.uid == userId;
      }
    }
  }
}
```

---

## 🌐 Google OAuth Setup (optional)

Only needed if you want **"Continue with Google"** to work.

1. Go to [https://console.cloud.google.com](https://console.cloud.google.com) and open the same project.
2. Navigate to **APIs & Services → Credentials**.
3. Click **Create Credentials → OAuth client ID**.
4. Application type: **Desktop app**. Give it a name and click **Create**.
5. Copy the **Client ID** and **Client secret**.

---

## 🔑 Environment Variables

```bash
# Copy the example file
cp .env.example .env
```

Open `.env` and fill in your values:

```env
FIREBASE_API_KEY=AIzaSy...
FIREBASE_PROJECT_ID=your-project-id

# Only needed for Google OAuth
GOOGLE_CLIENT_ID=xxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-...
```

**Never commit `.env` to version control.**

---

## 📦 Installation

```bash
# 1. Create and activate a virtual environment (recommended)
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
```

---

## ▶️ Running the Application

```bash
python main.py
```

---

## 🔐 Security Architecture

| Concern | Implementation |
|---|---|
| Password storage | AES-256-GCM, unique 12-byte nonce per entry |
| Key derivation | PBKDF2-HMAC-SHA256, 600 000 iterations, 32-byte key |
| Master PIN hashing | bcrypt, cost factor 12 |
| Transport | HTTPS to Firebase / Google APIs |
| Vault auto-lock | 5-minute inactivity timeout |
| Plaintext in memory | Cleared on logout / lock |

> **Note on key derivation salt:** The current implementation derives the AES key
> from the Master PIN using the Firebase UID as the salt for simplicity.
> In a production deployment, generate a random 32-byte salt per user, store it
> alongside `masterPinHash` in Firestore, and fetch it at unlock time.

---

## 📤 Import / Export

### Export
1. Go to **Settings → Export Vault**.
2. Enter your Master PIN to confirm.
3. Choose a save location — an encrypted JSON file is written.

### Import
1. Go to **Settings → Import Vault**.
2. Select the JSON file.
3. Enter the **PIN that was used when exporting** (may differ from current PIN).
4. Entries are merged into your existing vault.

### Export file format

```json
{
  "salt": "<base64-encoded 32 bytes>",
  "entries": [
    {
      "site": "GitHub",
      "username": "alice@example.com",
      "password": "{\"ciphertext\": \"...\", \"nonce\": \"...\"}",
      "url": "https://github.com",
      "notes": ""
    }
  ]
}
```

---

## 🏗️ Building a Standalone Executable (PyInstaller)

```bash
pip install pyinstaller

# Windows (.exe)
pyinstaller --onefile --windowed --name VaultKey \
  --add-data "assets;assets" \
  main.py

# macOS (.app)
pyinstaller --onefile --windowed --name VaultKey \
  --add-data "assets:assets" \
  main.py
```

The executable will be in the `dist/` folder.

> **Tip:** Bundle your `.env` values as build-time constants instead of shipping
> a `.env` file with the executable to avoid exposing credentials.

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+F` | Focus search bar |
| `Ctrl+C` | Copy selected text |

---

## 🗂️ Firestore Document Structure

```
users/
└── {userId}/
    ├── masterPinHash: "<bcrypt hash>"
    └── vault/
        └── {entryId}/
            ├── site:      "GitHub"
            ├── username:  "alice@example.com"
            ├── password:  '{"ciphertext":"...","nonce":"..."}'
            ├── url:       "https://github.com"
            └── notes:     ""
```

---

## 📝 License

MIT – use freely, modify as needed.
