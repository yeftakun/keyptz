import json
import keyboard
import vgamepad as vg
import time
import os
import threading
import ctypes
import webbrowser
import pystray
import tkinter as tk
from tkinter import ttk, messagebox
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

# --- 2. MAPPING KONSTANTA & DEFAULT PROFILE ---
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

DEFAULT_PROFILE = {
    "hold_control": False,
    "modifier_key": "0",
    "boost_key": "enter",
    "boost_multiplier": 1.2,
    "buttons": {
        "DPAD_UP": "", "DPAD_DOWN": "", "DPAD_LEFT": "", "DPAD_RIGHT": "",
        "START": "", "BACK": "", "LEFT_THUMB_CLICK": "", "RIGHT_THUMB_CLICK": "",
        "LEFT_BUMPER": "", "RIGHT_BUMPER": "", "GUIDE": "",
        "A": "Tab", "B": "", "X": "", "Y": ""
    },
    "triggers": {
        "LEFT_TRIGGER": { "keys": [""], "value": "26" },
        "RIGHT_TRIGGER": { "keys": [""], "value": "26" }
    },
    "joysticks": {
        "LEFT_X_MIN": { "keys": ["4"], "value": "26" },
        "LEFT_X_MAX": { "keys": ["6"], "value": "26" },
        "LEFT_Y_MIN": { "keys": ["2"], "value": "26" },
        "LEFT_Y_MAX": { "keys": ["8"], "value": "26" },
        "RIGHT_X_MIN": { "keys": [""], "value": "26" },
        "RIGHT_X_MAX": { "keys": [""], "value": "26" },
        "RIGHT_Y_MIN": { "keys": ["-"], "value": "26" },
        "RIGHT_Y_MAX": { "keys": ["+"], "value": "26" }
    }
}

is_running = True
is_gui_open = False
gamepad = None

# --- 3. FUNGSI UTILITAS & UI ---
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

def show_startup_alert():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    messagebox.showinfo("Sukses", "KeyPTZ berjalan")
    root.destroy()

def show_already_running_alert():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    messagebox.showwarning("Peringatan", "KeyPTZ sebelumnya sudah berjalan")
    root.destroy()

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

    latched_lx, latched_ly, latched_rx, latched_ry = 0, 0, 0, 0
    latched_lt, latched_rt = 0, 0
    latched_btns = set()

    while is_running:
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

        hold_ctrl = config.get("hold_control", False)
        mod_key = config.get("modifier_key", "")
        boost_key = config.get("boost_key", "")
        try: boost_mult = float(config.get("boost_multiplier", 1.0))
        except: boost_mult = 1.0

        btn_conf = config.get("buttons", {})
        trg_conf = config.get("triggers", {})
        joy_conf = config.get("joysticks", {})

        phys_state = get_physical_gamepad_state(virtual_slot)
        
        is_mod_pressed = is_pressed(mod_key)
        is_boost_pressed = is_pressed(boost_key)
        
        kb_active_normal = not mod_key or is_mod_pressed
        kb_active = kb_active_normal or is_boost_pressed
        
        lx_kb, ly_kb, rx_kb, ry_kb, lt_kb, rt_kb = 0, 0, 0, 0, 0, 0
        
        if kb_active:
            current_mult = boost_mult if is_boost_pressed else 1.0

            cur_btns = set()
            for xbox_btn, kb_key in btn_conf.items():
                if is_pressed(kb_key) and BTN_MAP.get(xbox_btn):
                    cur_btns.add(BTN_MAP[xbox_btn])
                    
            cur_lt, cur_rt = 0, 0
            lt_key = trg_conf.get("LEFT_TRIGGER", {}).get("keys", "")
            if is_pressed(lt_key): cur_lt = parse_percentage(trg_conf.get("LEFT_TRIGGER", {}).get("value", "100%"), 255)
            rt_key = trg_conf.get("RIGHT_TRIGGER", {}).get("keys", "")
            if is_pressed(rt_key): cur_rt = parse_percentage(trg_conf.get("RIGHT_TRIGGER", {}).get("value", "100%"), 255)

            cur_lx, cur_ly, cur_rx, cur_ry = 0, 0, 0, 0
            if is_pressed(joy_conf.get("LEFT_X_MIN", {}).get("keys", "")): cur_lx = parse_percentage(joy_conf.get("LEFT_X_MIN", {}).get("value", "100%"), -32768)
            elif is_pressed(joy_conf.get("LEFT_X_MAX", {}).get("keys", "")): cur_lx = parse_percentage(joy_conf.get("LEFT_X_MAX", {}).get("value", "100%"), 32767)
            if is_pressed(joy_conf.get("LEFT_Y_MIN", {}).get("keys", "")): cur_ly = parse_percentage(joy_conf.get("LEFT_Y_MIN", {}).get("value", "100%"), -32768)
            elif is_pressed(joy_conf.get("LEFT_Y_MAX", {}).get("keys", "")): cur_ly = parse_percentage(joy_conf.get("LEFT_Y_MAX", {}).get("value", "100%"), 32767)

            if is_pressed(joy_conf.get("RIGHT_X_MIN", {}).get("keys", "")): cur_rx = parse_percentage(joy_conf.get("RIGHT_X_MIN", {}).get("value", "100%"), -32768)
            elif is_pressed(joy_conf.get("RIGHT_X_MAX", {}).get("keys", "")): cur_rx = parse_percentage(joy_conf.get("RIGHT_X_MAX", {}).get("value", "100%"), 32767)
            if is_pressed(joy_conf.get("RIGHT_Y_MIN", {}).get("keys", "")): cur_ry = parse_percentage(joy_conf.get("RIGHT_Y_MIN", {}).get("value", "100%"), -32768)
            elif is_pressed(joy_conf.get("RIGHT_Y_MAX", {}).get("keys", "")): cur_ry = parse_percentage(joy_conf.get("RIGHT_Y_MAX", {}).get("value", "100%"), 32767)

            if hold_ctrl:
                if cur_btns: latched_btns.update(cur_btns)
                
                if cur_lt != 0 or cur_rt != 0:
                    latched_lt, latched_rt = cur_lt, cur_rt
                    
                if cur_lx != 0 or cur_ly != 0:
                    latched_lx, latched_ly = cur_lx, cur_ly
                    
                if cur_rx != 0 or cur_ry != 0:
                    latched_rx, latched_ry = cur_rx, cur_ry
            else:
                latched_btns = cur_btns
                latched_lt, latched_rt = cur_lt, cur_rt
                latched_lx, latched_ly = cur_lx, cur_ly
                latched_rx, latched_ry = cur_rx, cur_ry

            lt_kb = min(255, int(latched_lt * current_mult))
            rt_kb = min(255, int(latched_rt * current_mult))
            
            lx_kb = max(-32768, min(32767, int(latched_lx * current_mult)))
            ly_kb = max(-32768, min(32767, int(latched_ly * current_mult)))
            rx_kb = max(-32768, min(32767, int(latched_rx * current_mult)))
            ry_kb = max(-32768, min(32767, int(latched_ry * current_mult)))

        else:
            latched_btns.clear()
            latched_lt, latched_rt = 0, 0
            latched_lx, latched_ly, latched_rx, latched_ry = 0, 0, 0, 0
            lx_kb, ly_kb, rx_kb, ry_kb, lt_kb, rt_kb = 0, 0, 0, 0, 0, 0

        for btn_name, btn_val in BTN_MAP.items():
            is_phys = phys_state and (phys_state.wButtons & btn_val)
            if (btn_val in latched_btns) or is_phys:
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


# --- 5. GUI EDITOR DENGAN KEY CATCHER & PROFILE SYSTEM ---

class KeyAssigner:
    """Kelas untuk menangani penangkapan tombol keyboard selama 5 detik"""
    def __init__(self, root):
        self.root = root
        self.hook = None
        self.timeout_id = None
        self.target_var = None
        self.is_append = False
        self.old_val = ""

    def start(self, var, append=False):
        self.cancel() # Batalkan penangkapan sebelumnya jika ada
        self.target_var = var
        self.is_append = append
        self.old_val = var.get()
        
        var.set("< Menunggu 5d... >")
        
        # Jeda mikro agar klik mouse/tombol sebelumnya tidak ikut tertangkap
        self.root.after(200, self._start_hook)
        # Mulai hitung mundur 5 detik
        self.timeout_id = self.root.after(5000, self._timeout)

    def _start_hook(self):
        self.captured = False
        self.hook = keyboard.on_press(self._on_press)

    def _on_press(self, event):
        if self.captured: return
        self.captured = True
        # Lempar kembali ke GUI Thread agar aman
        self.root.after(0, self._finish, event.name)

    def _finish(self, key_name):
        self._cleanup()
        
        # Jika tombol Escape ditekan, batalkan pengisian
        if key_name.lower() == 'esc':
            self.target_var.set(self.old_val)
            return

        # Format Append (Multiple Keys) atau Replace
        if self.is_append and self.old_val:
            existing = [k.strip() for k in self.old_val.split(',')]
            if key_name not in existing:
                self.target_var.set(self.old_val + f", {key_name}")
            else:
                self.target_var.set(self.old_val)
        else:
            self.target_var.set(key_name)

    def _timeout(self):
        self._cleanup()
        self.target_var.set(self.old_val)
        messagebox.showinfo("Timeout", "Waktu habis! Tidak ada tombol yang ditekan.")

    def _cleanup(self):
        if self.hook:
            try:
                keyboard.unhook(self.hook)
            except: pass
            self.hook = None
        if self.timeout_id:
            self.root.after_cancel(self.timeout_id)
            self.timeout_id = None

    def cancel(self):
        if self.target_var:
            self._cleanup()
            self.target_var.set(self.old_val)
            self.target_var = None


def config_gui_thread():
    global is_gui_open
    
    base_path = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(base_path, "config.json")
    profile_dir = os.path.join(base_path, "profile")
    
    os.makedirs(profile_dir, exist_ok=True)
    
    with open(config_file, "r") as f:
        cfg = json.load(f)

    root = tk.Tk()
    root.title("KeyPTZ - Config & Profile Editor")
    root.geometry("560x580") # Diperlebar sedikit untuk tombol baru
    root.resizable(False, False)
    root.attributes("-topmost", True)
    
    assigner = KeyAssigner(root)

    def on_closing():
        global is_gui_open
        assigner.cancel()
        is_gui_open = False
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_closing)

    notebook = ttk.Notebook(root)
    notebook.pack(fill='both', expand=True, padx=10, pady=10)

    # --- TAB GENERAL ---
    v_hold = tk.BooleanVar(value=cfg.get("hold_control", False))
    v_mod = tk.StringVar(value=cfg.get("modifier_key", ""))
    v_boost = tk.StringVar(value=cfg.get("boost_key", ""))
    v_mult = tk.StringVar(value=str(cfg.get("boost_multiplier", 1.2)))

    f_gen = ttk.Frame(notebook)
    notebook.add(f_gen, text="General")
    ttk.Checkbutton(f_gen, text="Enable Hold/Cruise Control", variable=v_hold).pack(anchor="w", pady=5, padx=10)
    
    frame_grid1 = ttk.Frame(f_gen)
    frame_grid1.pack(fill="x", padx=10, pady=5)
    
    # Setup Input Modifier Key
    ttk.Label(frame_grid1, text="Modifier (Kopling) Key:").grid(row=0, column=0, sticky="w", pady=2)
    f_mod = ttk.Frame(frame_grid1)
    f_mod.grid(row=0, column=1, sticky="w")
    ttk.Entry(f_mod, textvariable=v_mod, width=15, state="readonly").pack(side="left", padx=2)
    ttk.Button(f_mod, text="Insert", width=6, command=lambda: assigner.start(v_mod)).pack(side="left")
    ttk.Button(f_mod, text="X", width=2, command=lambda: v_mod.set("")).pack(side="left")

    # Setup Input Boost Key
    ttk.Label(frame_grid1, text="Boost (Turbo) Key:").grid(row=1, column=0, sticky="w", pady=2)
    f_bst = ttk.Frame(frame_grid1)
    f_bst.grid(row=1, column=1, sticky="w")
    ttk.Entry(f_bst, textvariable=v_boost, width=15, state="readonly").pack(side="left", padx=2)
    ttk.Button(f_bst, text="Insert", width=6, command=lambda: assigner.start(v_boost)).pack(side="left")
    ttk.Button(f_bst, text="X", width=2, command=lambda: v_boost.set("")).pack(side="left")

    # Setup Multiplier (Tetap manual karena angka)
    ttk.Label(frame_grid1, text="Boost Multiplier (e.g. 1.5):").grid(row=2, column=0, sticky="w", pady=2)
    ttk.Entry(frame_grid1, textvariable=v_mult, width=15).grid(row=2, column=1, sticky="w", padx=2, pady=2)


    # --- TAB BUTTONS ---
    f_btn = ttk.Frame(notebook)
    notebook.add(f_btn, text="Buttons")
    btn_canvas = tk.Canvas(f_btn)
    scrollbar = ttk.Scrollbar(f_btn, orient="vertical", command=btn_canvas.yview)
    scrollable_frame = ttk.Frame(btn_canvas)
    scrollable_frame.bind("<Configure>", lambda e: btn_canvas.configure(scrollregion=btn_canvas.bbox("all")))
    btn_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    btn_canvas.configure(yscrollcommand=scrollbar.set)
    btn_canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    btn_vars = {}
    for i, btn in enumerate(BTN_MAP.keys()):
        ttk.Label(scrollable_frame, text=btn).grid(row=i, column=0, sticky="w", padx=5, pady=2)
        
        val = cfg.get("buttons", {}).get(btn, "")
        var = tk.StringVar(value=val)
        btn_vars[btn] = var
        
        f_b = ttk.Frame(scrollable_frame)
        f_b.grid(row=i, column=1, sticky="w", padx=5)
        ttk.Entry(f_b, textvariable=var, width=20, state="readonly").pack(side="left", padx=2)
        
        # PENTING: Gunakan default parameter 'v=var' di lambda agar tidak ketimpa loop terakhir
        ttk.Button(f_b, text="Insert", width=6, command=lambda v=var: assigner.start(v)).pack(side="left")
        ttk.Button(f_b, text="X", width=2, command=lambda v=var: v.set("")).pack(side="left")

    # --- TAB ANALOG & TRIGGERS ---
    f_analog = ttk.Frame(notebook)
    notebook.add(f_analog, text="Analog & Triggers")
    
    ttk.Label(f_analog, text="AXIS / TRIGGER", font=("", 9, "bold")).grid(row=1, column=0, sticky="w", padx=5)
    ttk.Label(f_analog, text="KEYS MAP", font=("", 9, "bold")).grid(row=1, column=1, sticky="w", padx=5)
    ttk.Label(f_analog, text="VALUE %", font=("", 9, "bold")).grid(row=1, column=2, sticky="w", padx=5)

    analog_vars = {}
    analog_items = list(cfg.get("joysticks", {}).items()) + list(cfg.get("triggers", {}).items())
    
    for i, (name, data) in enumerate(analog_items):
        ttk.Label(f_analog, text=name).grid(row=i+2, column=0, sticky="w", padx=5, pady=2)
        
        keys_str = ", ".join(data.get("keys", [""]))
        var_keys = tk.StringVar(value=keys_str)
        var_val = tk.StringVar(value=data.get("value", "100%"))
        analog_vars[name] = {"keys": var_keys, "value": var_val}

        f_a = ttk.Frame(f_analog)
        f_a.grid(row=i+2, column=1, sticky="w", padx=5)
        
        ttk.Entry(f_a, textvariable=var_keys, width=16, state="readonly").pack(side="left", padx=2)
        ttk.Button(f_a, text="Insert", width=6, command=lambda v=var_keys: assigner.start(v)).pack(side="left")
        ttk.Button(f_a, text="+", width=2, command=lambda v=var_keys: assigner.start(v, append=True)).pack(side="left")
        ttk.Button(f_a, text="X", width=2, command=lambda v=var_keys: v.set("")).pack(side="left")
        
        # Value bisa diketik manual
        ttk.Entry(f_analog, textvariable=var_val, width=8).grid(row=i+2, column=2, padx=5, pady=2)

    def update_gui_from_dict(p_cfg, alert_name="Profile"):
        v_hold.set(p_cfg.get("hold_control", False))
        v_mod.set(p_cfg.get("modifier_key", ""))
        v_boost.set(p_cfg.get("boost_key", ""))
        v_mult.set(str(p_cfg.get("boost_multiplier", 1.2)))

        for btn in BTN_MAP.keys():
            val = p_cfg.get("buttons", {}).get(btn, "")
            btn_vars[btn].set(val)

        for name, vars_dict in analog_vars.items():
            if "TRIGGER" in name: data = p_cfg.get("triggers", {}).get(name, {})
            else: data = p_cfg.get("joysticks", {}).get(name, {})
            
            keys_str = ", ".join(data.get("keys", [""]))
            vars_dict["keys"].set(keys_str)
            vars_dict["value"].set(data.get("value", "100%"))

        messagebox.showinfo("Dimuat", f"'{alert_name}' telah dimuat ke editor.\nKlik 'Save & Apply' untuk mengaktifkannya.")

    def load_default_profile():
        update_gui_from_dict(DEFAULT_PROFILE, "Default (Bawaan)")

    # --- TAB PROFILES ---
    f_prof = ttk.Frame(notebook)
    notebook.add(f_prof, text="Profiles")
    
    ttk.Button(f_prof, text="Load Default Profile (Reset)", command=load_default_profile).pack(fill="x", padx=10, pady=(10, 5))
    ttk.Separator(f_prof, orient='horizontal').pack(fill='x', pady=5, padx=10)

    ttk.Label(f_prof, text="Available Profiles:", font=("", 10, "bold")).pack(anchor="w", padx=10)
    
    listbox_frame = ttk.Frame(f_prof)
    listbox_frame.pack(fill="both", expand=True, padx=10, pady=5)
    profile_listbox = tk.Listbox(listbox_frame, height=6)
    profile_listbox.pack(side="left", fill="both", expand=True)
    listbox_scroll = ttk.Scrollbar(listbox_frame, orient="vertical", command=profile_listbox.yview)
    listbox_scroll.pack(side="right", fill="y")
    profile_listbox.config(yscrollcommand=listbox_scroll.set)

    def refresh_profile_list():
        profile_listbox.delete(0, tk.END)
        for file in os.listdir(profile_dir):
            if file.endswith(".json"):
                profile_listbox.insert(tk.END, file)

    refresh_profile_list()

    def get_current_gui_state():
        try: mult_val = float(v_mult.get())
        except: mult_val = 1.0

        new_cfg = {
            "hold_control": v_hold.get(),
            "modifier_key": v_mod.get().strip(),
            "boost_key": v_boost.get().strip(),
            "boost_multiplier": mult_val,
            "buttons": {k: v.get().strip() for k, v in btn_vars.items()},
            "triggers": {},
            "joysticks": {}
        }
        for name, vars_dict in analog_vars.items():
            keys_list = [k.strip() for k in vars_dict["keys"].get().split(',')]
            if not keys_list or keys_list == [""]: keys_list = [""]
            data = {"keys": keys_list, "value": vars_dict["value"].get().strip()}
            if "TRIGGER" in name: new_cfg["triggers"][name] = data
            else: new_cfg["joysticks"][name] = data
        return new_cfg

    def load_selected_profile():
        sel = profile_listbox.curselection()
        if not sel:
            messagebox.showwarning("Pilih Profile", "Pilih profile dari daftar terlebih dahulu!")
            return
        
        p_name = profile_listbox.get(sel[0])
        p_path = os.path.join(profile_dir, p_name)
        
        with open(p_path, "r") as f:
            p_cfg = json.load(f)

        update_gui_from_dict(p_cfg, f"Profile '{p_name}'")

    def save_as_new_profile():
        p_name = entry_new_prof.get().strip()
        if not p_name:
            messagebox.showwarning("Nama Kosong", "Masukkan nama profile baru!")
            return
            
        if p_name.lower() in ["default", "default.json"]:
            messagebox.showwarning("Ditolak", "Nama 'Default' dilindungi dan tidak bisa ditimpa. Gunakan nama lain.")
            return
            
        if not p_name.lower().endswith(".json"):
            p_name += ".json"
            
        p_path = os.path.join(profile_dir, p_name)
        new_cfg = get_current_gui_state()
        
        with open(p_path, "w") as f:
            json.dump(new_cfg, f, indent=4)
            
        entry_new_prof.delete(0, tk.END)
        refresh_profile_list()
        messagebox.showinfo("Tersimpan", f"Profile disimpan sebagai '{p_name}'.")

    def delete_selected_profile():
        sel = profile_listbox.curselection()
        if not sel: return
        p_name = profile_listbox.get(sel[0])
        if messagebox.askyesno("Konfirmasi", f"Hapus profile '{p_name}'?"):
            os.remove(os.path.join(profile_dir, p_name))
            refresh_profile_list()

    ttk.Button(f_prof, text="Load Selected Profile to Editor", command=load_selected_profile).pack(fill="x", padx=10, pady=2)
    ttk.Button(f_prof, text="Delete Selected Profile", command=delete_selected_profile).pack(fill="x", padx=10, pady=2)
    
    ttk.Separator(f_prof, orient='horizontal').pack(fill='x', pady=10, padx=10)
    
    ttk.Label(f_prof, text="Save Current Editor as New Profile:").pack(anchor="w", padx=10)
    entry_new_prof = ttk.Entry(f_prof)
    entry_new_prof.pack(fill="x", padx=10, pady=2)
    ttk.Button(f_prof, text="Save As New Profile", command=save_as_new_profile).pack(fill="x", padx=10, pady=2)

    # --- SAVE BUTTON GLOBAL ---
    def save_and_close():
        global is_gui_open
        assigner.cancel()
        new_cfg = get_current_gui_state()

        with open(config_file, "w") as f:
            json.dump(new_cfg, f, indent=4)
        
        is_gui_open = False
        root.destroy()
        
        msg_root = tk.Tk(); msg_root.withdraw(); msg_root.attributes("-topmost", True)
        messagebox.showinfo("Tersimpan", "Config Active berhasil diperbarui!\n(Hot-Reload menyala)")
        msg_root.destroy()

    f_btn_bot = ttk.Frame(root)
    f_btn_bot.pack(fill="x", side="bottom", pady=10)
    ttk.Button(f_btn_bot, text="Save & Apply (Active Config)", command=save_and_close).pack(pady=5)

    root.mainloop()

# --- 6. SYSTEM TRAY UI & PENCEGAH MULTIPLE INSTANCE ---
def show_startup_alert():
    root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
    messagebox.showinfo("Sukses", "KeyPTZ berjalan di Background")
    root.destroy()

def show_already_running_alert():
    root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
    messagebox.showwarning("Peringatan", "KeyPTZ sebelumnya sudah berjalan!")
    root.destroy()

def create_image():
    image = Image.new('RGB', (64, 64), color='black')
    dc = ImageDraw.Draw(image)
    dc.ellipse((10, 10, 54, 54), fill='green')
    return image

def open_github(icon, item):
    webbrowser.open("https://github.com/yeftakun/key2xbox")

def open_config(icon, item):
    global is_gui_open
    if not is_gui_open:
        is_gui_open = True
        threading.Thread(target=config_gui_thread, daemon=True).start()

def exit_action(icon, item):
    global is_running
    is_running = False  
    icon.stop()         

def check_single_instance():
    mutex_name = "KeyPTZ_vMix_Controller_Mutex_12345"
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, mutex_name)
    if kernel32.GetLastError() == 183:
        return False, None
    return True, mutex

def main():
    is_first_instance, mutex = check_single_instance()
    
    if not is_first_instance:
        show_already_running_alert()
        return

    show_startup_alert()

    ptz_thread = threading.Thread(target=ptz_controller_loop, daemon=True)
    ptz_thread.start()

    tray_menu = pystray.Menu(
        item('Config Key', open_config),
        item('GitHub', open_github),
        item('Exit', exit_action)
    )
    tray_icon = pystray.Icon("PTZController", create_image(), "vMix PTZ Controller", tray_menu)
    tray_icon.run()

if __name__ == "__main__":
    main()