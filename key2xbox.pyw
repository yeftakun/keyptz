import json
import keyboard
import vgamepad as vg
import time
import os
import threading
import ctypes
import webbrowser
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw

# --- 1. SETUP XINPUT API UNTUK MEMBACA STIK FISIK ---
xinput = None
for dll in ('xinput1_4.dll', 'xinput9_1_0.dll', 'xinput1_3.dll'):
    try:
        xinput = ctypes.windll.LoadLibrary(dll)
        break
    except OSError:
        continue

class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ("wButtons", ctypes.c_ushort),
        ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]

class XINPUT_STATE(ctypes.Structure):
    _fields_ = [("dwPacketNumber", ctypes.c_ulong), ("Gamepad", XINPUT_GAMEPAD)]

def get_connected_slots():
    connected = set()
    if not xinput: return connected
    for i in range(4):
        state = XINPUT_STATE()
        if xinput.XInputGetState(i, ctypes.byref(state)) == 0:
            connected.add(i)
    return connected

def get_physical_gamepad_state(exclude_slot):
    if not xinput: return None
    for i in range(4):
        if i == exclude_slot: continue
        state = XINPUT_STATE()
        if xinput.XInputGetState(i, ctypes.byref(state)) == 0:
            return state.Gamepad
    return None

# --- 2. MAPPING KONSTANTA XBOX ---
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

is_running = True
gamepad = None

# --- 3. FUNGSI UTILITAS ---
def is_pressed(key_input):
    if not key_input: return False
    try:
        if isinstance(key_input, list):
            return any(keyboard.is_pressed(k) for k in key_input if k)
        return keyboard.is_pressed(key_input)
    except:
        return False

def parse_percentage(val_input, raw_limit):
    try:
        if isinstance(val_input, str):
            val_input = val_input.replace('%', '').strip()
        pct = max(0.0, min(100.0, float(val_input)))
        return int((pct / 100.0) * raw_limit)
    except:
        return raw_limit 

# --- 4. FUNGSI UTAMA (BACKGROUND PROCESS) ---
def ptz_controller_loop():
    global is_running, gamepad
    
    base_path = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(base_path, "config.json")
    
    if not os.path.exists(config_file):
        is_running = False
        return

    physical_slots_before = get_connected_slots()
    gamepad = vg.VX360Gamepad()
    
    time.sleep(1.0)
    current_slots = get_connected_slots()
    new_slots = current_slots - physical_slots_before
    virtual_slot = list(new_slots)[0] if len(new_slots) > 0 else -1

    last_modified_time = os.path.getmtime(config_file)
    with open(config_file, "r") as f: config = json.load(f)

    while is_running:
        # --- HOT RELOAD CONFIG ---
        try:
            current_modified_time = os.path.getmtime(config_file)
            if current_modified_time > last_modified_time:
                time.sleep(0.05)
                try:
                    with open(config_file, "r") as f: config = json.load(f)
                    last_modified_time = current_modified_time
                except:
                    last_modified_time = current_modified_time
        except: pass 

        mod_key = config.get("modifier_key", "")
        boost_key = config.get("boost_key", "")
        try:
            boost_mult = float(config.get("boost_multiplier", 1.0))
        except:
            boost_mult = 1.0

        btn_conf = config.get("buttons", {})
        trg_conf = config.get("triggers", {})
        joy_conf = config.get("joysticks", {})

        phys_state = get_physical_gamepad_state(virtual_slot)
        kb_active = not mod_key or is_pressed(mod_key)
        
        kb_btns = {}
        lx_kb, ly_kb, rx_kb, ry_kb, lt_kb, rt_kb = 0, 0, 0, 0, 0, 0
        
        if kb_active:
            # Pengecekan status tombol Boost/Turbo
            current_mult = boost_mult if is_pressed(boost_key) else 1.0

            for xbox_btn, kb_key in btn_conf.items():
                if is_pressed(kb_key) and BTN_MAP.get(xbox_btn):
                    kb_btns[BTN_MAP[xbox_btn]] = True
                    
            lt_key = trg_conf.get("LEFT_TRIGGER", {}).get("keys", "")
            if is_pressed(lt_key): lt_kb = parse_percentage(trg_conf.get("LEFT_TRIGGER", {}).get("value", "100%"), 255)
            
            rt_key = trg_conf.get("RIGHT_TRIGGER", {}).get("keys", "")
            if is_pressed(rt_key): rt_kb = parse_percentage(trg_conf.get("RIGHT_TRIGGER", {}).get("value", "100%"), 255)

            if is_pressed(joy_conf.get("LEFT_X_MIN", {}).get("keys", "")): lx_kb = parse_percentage(joy_conf.get("LEFT_X_MIN", {}).get("value", "100%"), -32768)
            elif is_pressed(joy_conf.get("LEFT_X_MAX", {}).get("keys", "")): lx_kb = parse_percentage(joy_conf.get("LEFT_X_MAX", {}).get("value", "100%"), 32767)
            
            if is_pressed(joy_conf.get("LEFT_Y_MIN", {}).get("keys", "")): ly_kb = parse_percentage(joy_conf.get("LEFT_Y_MIN", {}).get("value", "100%"), -32768)
            elif is_pressed(joy_conf.get("LEFT_Y_MAX", {}).get("keys", "")): ly_kb = parse_percentage(joy_conf.get("LEFT_Y_MAX", {}).get("value", "100%"), 32767)

            if is_pressed(joy_conf.get("RIGHT_X_MIN", {}).get("keys", "")): rx_kb = parse_percentage(joy_conf.get("RIGHT_X_MIN", {}).get("value", "100%"), -32768)
            elif is_pressed(joy_conf.get("RIGHT_X_MAX", {}).get("keys", "")): rx_kb = parse_percentage(joy_conf.get("RIGHT_X_MAX", {}).get("value", "100%"), 32767)
            
            if is_pressed(joy_conf.get("RIGHT_Y_MIN", {}).get("keys", "")): ry_kb = parse_percentage(joy_conf.get("RIGHT_Y_MIN", {}).get("value", "100%"), -32768)
            elif is_pressed(joy_conf.get("RIGHT_Y_MAX", {}).get("keys", "")): ry_kb = parse_percentage(joy_conf.get("RIGHT_Y_MAX", {}).get("value", "100%"), 32767)

            # --- APLIKASIKAN BOOST MULTIPLIER & CLAMPING ---
            lt_kb = min(255, int(lt_kb * current_mult))
            rt_kb = min(255, int(rt_kb * current_mult))
            
            lx_kb = max(-32768, min(32767, int(lx_kb * current_mult)))
            ly_kb = max(-32768, min(32767, int(ly_kb * current_mult)))
            rx_kb = max(-32768, min(32767, int(rx_kb * current_mult)))
            ry_kb = max(-32768, min(32767, int(ry_kb * current_mult)))

        # --- C. PENGGABUNGAN (MERGE) & UPDATE KE VIRTUAL GAMEPAD ---
        for btn_name, btn_val in BTN_MAP.items():
            is_phys = phys_state and (phys_state.wButtons & btn_val)
            if kb_btns.get(btn_val) or is_phys:
                gamepad.press_button(button=btn_val)
            else:
                gamepad.release_button(button=btn_val)

        lt_phys = phys_state.bLeftTrigger if phys_state else 0
        rt_phys = phys_state.bRightTrigger if phys_state else 0
        gamepad.left_trigger(value=max(lt_kb, lt_phys))
        gamepad.right_trigger(value=max(rt_kb, rt_phys))

        lx_phys = phys_state.sThumbLX if phys_state else 0
        ly_phys = phys_state.sThumbLY if phys_state else 0
        rx_phys = phys_state.sThumbRX if phys_state else 0
        ry_phys = phys_state.sThumbRY if phys_state else 0

        final_lx = max(-32768, min(32767, lx_kb + lx_phys))
        final_ly = max(-32768, min(32767, ly_kb + ly_phys))
        final_rx = max(-32768, min(32767, rx_kb + rx_phys))
        final_ry = max(-32768, min(32767, ry_kb + ry_phys))

        gamepad.left_joystick(x_value=final_lx, y_value=final_ly)
        gamepad.right_joystick(x_value=final_rx, y_value=final_ry)

        gamepad.update()
        time.sleep(0.01)
        
    if gamepad:
        gamepad.reset()
        gamepad.update()

# --- 5. SYSTEM TRAY UI ---
def create_image():
    image = Image.new('RGB', (64, 64), color='black')
    dc = ImageDraw.Draw(image)
    dc.ellipse((10, 10, 54, 54), fill='green')
    return image

def open_github(icon, item):
    webbrowser.open("https://github.com/yeftakun/key2xbox")

def exit_action(icon, item):
    global is_running
    is_running = False  
    icon.stop()         

def main():
    ptz_thread = threading.Thread(target=ptz_controller_loop, daemon=True)
    ptz_thread.start()

    tray_menu = pystray.Menu(
        item('GitHub Repository', open_github),
        item('Quit / Exit PTZ', exit_action)
    )
    tray_icon = pystray.Icon("PTZController", create_image(), "vMix PTZ Controller", tray_menu)
    tray_icon.run()

if __name__ == "__main__":
    main()