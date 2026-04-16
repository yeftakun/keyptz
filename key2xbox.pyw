import json
import keyboard
import vgamepad as vg
import time
import os
import threading
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw

# --- MAPPING KONSTANTA XBOX ---
BTN_MAP = {
    "DPAD_UP": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
    "DPAD_DOWN": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
    "DPAD_LEFT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
    "DPAD_RIGHT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
    "START": vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
    "BACK": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
    "LEFT_THUMB_CLICK": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
    "RIGHT_THUMB_CLICK": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
    "LEFT_BUMPER": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
    "RIGHT_BUMPER": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
    "GUIDE": vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
    "A": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
    "B": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
    "X": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
    "Y": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y
}

# --- VARIABEL GLOBAL UNTUK KONTROL BACKGROUND ---
is_running = True
gamepad = None

def is_pressed(key_input):
    if not key_input: 
        return False
    try:
        if isinstance(key_input, list):
            return any(keyboard.is_pressed(k) for k in key_input if k)
        else:
            return keyboard.is_pressed(key_input)
    except:
        return False

def parse_percentage(val_input, raw_limit):
    try:
        if isinstance(val_input, str):
            val_input = val_input.replace('%', '').strip()
        pct = float(val_input)
        pct = max(0.0, min(100.0, pct))
        return int((pct / 100.0) * raw_limit)
    except (ValueError, TypeError):
        return raw_limit 

# --- FUNGSI UTAMA (BERJALAN DI BACKGROUND THREAD) ---
def ptz_controller_loop():
    global is_running, gamepad
    
    config_file = "config.json"
    
    if not os.path.exists(config_file):
        print(f"Error: File {config_file} tidak ditemukan!")
        is_running = False
        return

    with open(config_file, "r") as f:
        config = json.load(f)
        
    last_modified_time = os.path.getmtime(config_file)
    gamepad = vg.VX360Gamepad()
    
    mod_key = config.get("modifier_key", "")
    btn_conf = config.get("buttons", {})
    trg_conf = config.get("triggers", {})
    joy_conf = config.get("joysticks", {})

    while is_running:
        # --- HOT RELOAD LOGIC ---
        try:
            current_modified_time = os.path.getmtime(config_file)
            if current_modified_time > last_modified_time:
                time.sleep(0.05)
                try:
                    with open(config_file, "r") as f:
                        config = json.load(f)
                    mod_key = config.get("modifier_key", "")
                    btn_conf = config.get("buttons", {})
                    trg_conf = config.get("triggers", {})
                    joy_conf = config.get("joysticks", {})
                    last_modified_time = current_modified_time
                except json.JSONDecodeError:
                    last_modified_time = current_modified_time
        except FileNotFoundError:
            pass 

        # --- CONTROLLER LOGIC ---
        if not mod_key or is_pressed(mod_key):
            
            for xbox_btn, kb_key in btn_conf.items():
                if xbox_btn in BTN_MAP:
                    if is_pressed(kb_key):
                        gamepad.press_button(button=BTN_MAP[xbox_btn])
                    else:
                        gamepad.release_button(button=BTN_MAP[xbox_btn])

            lt_key = trg_conf.get("LEFT_TRIGGER", {}).get("keys", "")
            lt_val = parse_percentage(trg_conf.get("LEFT_TRIGGER", {}).get("value", "100%"), 255)
            rt_key = trg_conf.get("RIGHT_TRIGGER", {}).get("keys", "")
            rt_val = parse_percentage(trg_conf.get("RIGHT_TRIGGER", {}).get("value", "100%"), 255)

            gamepad.left_trigger(value=lt_val if is_pressed(lt_key) else 0)
            gamepad.right_trigger(value=rt_val if is_pressed(rt_key) else 0)

            lx, ly = 0, 0
            if is_pressed(joy_conf.get("LEFT_X_MIN", {}).get("keys", "")): 
                lx = parse_percentage(joy_conf.get("LEFT_X_MIN", {}).get("value", "100%"), -32768)
            elif is_pressed(joy_conf.get("LEFT_X_MAX", {}).get("keys", "")): 
                lx = parse_percentage(joy_conf.get("LEFT_X_MAX", {}).get("value", "100%"), 32767)
                
            if is_pressed(joy_conf.get("LEFT_Y_MIN", {}).get("keys", "")): 
                ly = parse_percentage(joy_conf.get("LEFT_Y_MIN", {}).get("value", "100%"), -32768)
            elif is_pressed(joy_conf.get("LEFT_Y_MAX", {}).get("keys", "")): 
                ly = parse_percentage(joy_conf.get("LEFT_Y_MAX", {}).get("value", "100%"), 32767)
                
            gamepad.left_joystick(x_value=lx, y_value=ly)

            rx, ry = 0, 0
            if is_pressed(joy_conf.get("RIGHT_X_MIN", {}).get("keys", "")): 
                rx = parse_percentage(joy_conf.get("RIGHT_X_MIN", {}).get("value", "100%"), -32768)
            elif is_pressed(joy_conf.get("RIGHT_X_MAX", {}).get("keys", "")): 
                rx = parse_percentage(joy_conf.get("RIGHT_X_MAX", {}).get("value", "100%"), 32767)
                
            if is_pressed(joy_conf.get("RIGHT_Y_MIN", {}).get("keys", "")): 
                ry = parse_percentage(joy_conf.get("RIGHT_Y_MIN", {}).get("value", "100%"), -32768)
            elif is_pressed(joy_conf.get("RIGHT_Y_MAX", {}).get("keys", "")): 
                ry = parse_percentage(joy_conf.get("RIGHT_Y_MAX", {}).get("value", "100%"), 32767)
                
            gamepad.right_joystick(x_value=rx, y_value=ry)

        else:
            # --- RESET NETRAL ---
            for xbox_btn in BTN_MAP.values():
                gamepad.release_button(button=xbox_btn)
            gamepad.left_trigger(value=0)
            gamepad.right_trigger(value=0)
            gamepad.left_joystick(x_value=0, y_value=0)
            gamepad.right_joystick(x_value=0, y_value=0)

        gamepad.update()
        time.sleep(0.01)
        
    # Jika is_running False (User klik Quit), matikan controller dengan aman
    if gamepad:
        gamepad.reset()
        gamepad.update()

# --- FUNGSI UNTUK MENGGAMBAR IKON SYSTEM TRAY ---
def create_image():
    # Membuat gambar kotak hitam dengan lingkaran hijau di tengah (Indikator Aktif)
    image = Image.new('RGB', (64, 64), color='black')
    dc = ImageDraw.Draw(image)
    dc.ellipse((10, 10, 54, 54), fill='green')
    return image

# --- AKSI SAAT TOMBOL QUIT DIKLIK ---
def exit_action(icon, item):
    global is_running
    is_running = False  # Menghentikan thread controller
    icon.stop()         # Menutup System Tray

def main():
    # 1. Jalankan fungsi PTZ di Background Thread
    ptz_thread = threading.Thread(target=ptz_controller_loop, daemon=True)
    ptz_thread.start()

    # 2. Buat dan jalankan Menu System Tray di Main Thread
    tray_menu = pystray.Menu(item('Quit / Exit PTZ', exit_action))
    tray_icon = pystray.Icon("PTZController", create_image(), "vMix PTZ Controller", tray_menu)
    
    # Perintah run() akan memblokir terminal, menjaganya tetap hidup di background
    tray_icon.run()

if __name__ == "__main__":
    main()