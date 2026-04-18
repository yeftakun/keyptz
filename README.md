# KeyPTZ - Keyboard to Virtual Xbox 360 Controller for vMix PTZ Control

Dibuat untuk fleksibilitas penggunaan keyboard sebagai pengontrol kamera PTZ di aplikasi vMix. Operator dapat dengan mudah mengubah input keyboard menjadi sinyal Virtual Xbox 360, memungkinkan pergerakan kamera yang lebih fleksibel.

**Fitur Utama:**
- Map keyboard ke xbox
- Virtual gamepad (xbox360). Ketika menggunakan gamepad fisik, tidak perlu restart vmix kalau perangkat terlepas
- Tombol pengaman & Boost
- Hold control
- Profile

### Requirements

Versi Python saya: 3.12.5

```
pip install keyboard vgamepad pystray Pillow
```

Khusus ketika membuat shortcut xbox untuk kamera PTZ di vmix, set persentase analog & trigger ke 100%.

⚠️Jalankan sebelum vmix; Jangan exit sebelum vmix dimatikan. 

### Referensi Shortcuts vMix PTZ Control
- Move camera & stop: **analog kiri** (8 arah)
- Zoom & stop: **analog kanan** (2 arah)
- Home: **tombol A**