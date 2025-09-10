from flask import Flask, request, jsonify, send_file
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import os, random, time

app = Flask(__name__)

@app.route("/README")
def get_readme():
    return send_file("/home/kali/padding/README.md", mimetype="text/markdown")

# ---------------------------
# Configuration (ENV toggles)
# ---------------------------
FLAG = os.environ.get("FLAG", None)  # Flag must be injected at runtime
if FLAG is None:
    raise RuntimeError("FLAG not set! Please run container with -e FLAG=...")

BONUS_FLAG = os.environ.get("BONUS_FLAG", "flag{wrong_wrong_wrong_but_at_least_consistent}")
SECRET_KEY = os.environ.get("SECRET_KEY", None)
NOISE_RATE = float(os.environ.get("NOISE_RATE", "0.00"))
REQUIRE_TOKEN = os.environ.get("REQUIRE_TOKEN", "false").lower() == "true"
API_TOKEN = os.environ.get("API_TOKEN", "bring-your-own-token")
BLOCK_SIZE = 16  # AES block size for CBC

# New hint for players
HINT = "The last byte has a secret to tell."

# Track error count
error_count = 0

# ---------------------------
# Helpers
# ---------------------------
if SECRET_KEY is None:
    SECRET_KEY = get_random_bytes(16)
else:
    try:
        SECRET_KEY = bytes.fromhex(SECRET_KEY)
    except ValueError:
        SECRET_KEY = SECRET_KEY.encode()

def pad(data: bytes) -> bytes:
    pad_len = BLOCK_SIZE - (len(data) % BLOCK_SIZE)
    return data + bytes([pad_len] * pad_len)

def unpad(data: bytes) -> bytes:
    if len(data) == 0:
        raise ValueError("Invalid padding")
    pad_len = data[-1]
    if pad_len < 1 or pad_len > BLOCK_SIZE:
        raise ValueError("Invalid padding")
    if data[-pad_len:] != bytes([pad_len] * pad_len):
        raise ValueError("Invalid padding")
    return data[:-pad_len]

def encrypt(plaintext: bytes):
    iv = get_random_bytes(BLOCK_SIZE)
    cipher = AES.new(SECRET_KEY, AES.MODE_CBC, iv)
    ct = cipher.encrypt(pad(plaintext))
    return iv, ct

def check_auth():
    if not REQUIRE_TOKEN:
        return True
    return request.headers.get("X-API-Key") == API_TOKEN

# ---------------------------
# Routes
# ---------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/get_ciphertext", methods=["GET"])
def get_ciphertext():
    if not check_auth():
        return jsonify({"result": "unauthorized"}), 401

    msg = (FLAG + "::" + "WELCOME_TO_PADDING_ORACLE!").encode()
    iv, ct = encrypt(msg)
    return jsonify({
        "iv": iv.hex(),
        "ciphertext": ct.hex(),
        "hint": "The last byte has a secret to tell."
    })

@app.route("/decrypt", methods=["POST"])
def decrypt():
    global error_count

    if not check_auth():
        return jsonify({"result": "unauthorized"}), 401

    if NOISE_RATE > 0 and random.random() < NOISE_RATE:
        time.sleep(0.05)
        return jsonify({"result": "Error"}), 500

    try:
        data = request.get_json(force=True, silent=False)
        iv_hex = data.get("iv", "")
        ct_hex = data.get("ciphertext", "")

        iv = bytes.fromhex(iv_hex)
        ct = bytes.fromhex(ct_hex)

        if len(iv) != BLOCK_SIZE or len(ct) == 0 or len(ct) % BLOCK_SIZE != 0:
            return jsonify({"result": "Invalid padding"}), 200

        cipher = AES.new(SECRET_KEY, AES.MODE_CBC, iv)
        plaintext = cipher.decrypt(ct)

        _ = unpad(plaintext)

        error_count = 0  # reset counter
        return jsonify({"result": "Valid padding"}), 200

    except ValueError:
        error_count += 1
        if error_count >= 3:
            error_count = 0
            return jsonify({
                "result": "Invalid padding",
                "bonus_flag": BONUS_FLAG
            }), 200
        return jsonify({"result": "Invalid padding"}), 200
    except Exception:
        return jsonify({"result": "Error"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
