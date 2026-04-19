# keyPTZ-desktop (.NET C#)

Version: v0.1.0

Rewrite dari project Python ke .NET C# (WinForms + System Tray) dengan fitur setara:

- Keyboard mapping ke virtual Xbox 360 controller
- Dukungan gamepad fisik + virtual secara bersamaan
- Modifier key, boost key, boost multiplier
- Hold/Cruise control
- Hot-reload `config.json`
- Editor config & profile dari tray
- Single-instance guard (mutex)

## Build & Run

```powershell
dotnet build
cd bin\Debug\net8.0-windows
dotnet keyPTZ-desktop.dll
```

Saat aplikasi berjalan, gunakan icon tray untuk membuka menu `Config`, `GitHub`, atau `Exit`.

## File Data

- `config.json`
- `profile/*.json`

Kedua lokasi ini berada di folder output aplikasi (`AppContext.BaseDirectory`).
