using Nefarius.ViGEm.Client;
using Nefarius.ViGEm.Client.Targets;
using Nefarius.ViGEm.Client.Targets.Xbox360;

namespace KeyPTZ.Desktop;

public sealed class ControllerService : IDisposable
{
    private readonly ConfigStore _configStore;
    private readonly AppPaths _paths;
    private readonly CancellationTokenSource _cts = new();
    private readonly object _lock = new();
    private Thread? _thread;
    private ViGEmClient? _client;
    private IXbox360Controller? _controller;

    private static readonly Dictionary<string, Xbox360Button> ButtonMap = new(StringComparer.OrdinalIgnoreCase)
    {
        ["DPAD_UP"] = Xbox360Button.Up,
        ["DPAD_DOWN"] = Xbox360Button.Down,
        ["DPAD_LEFT"] = Xbox360Button.Left,
        ["DPAD_RIGHT"] = Xbox360Button.Right,
        ["START"] = Xbox360Button.Start,
        ["BACK"] = Xbox360Button.Back,
        ["LEFT_THUMB_CLICK"] = Xbox360Button.LeftThumb,
        ["RIGHT_THUMB_CLICK"] = Xbox360Button.RightThumb,
        ["LEFT_BUMPER"] = Xbox360Button.LeftShoulder,
        ["RIGHT_BUMPER"] = Xbox360Button.RightShoulder,
        ["GUIDE"] = Xbox360Button.Guide,
        ["A"] = Xbox360Button.A,
        ["B"] = Xbox360Button.B,
        ["X"] = Xbox360Button.X,
        ["Y"] = Xbox360Button.Y
    };

    private static readonly Dictionary<string, ushort> PhysicalButtonMask = new(StringComparer.OrdinalIgnoreCase)
    {
        ["DPAD_UP"] = 0x0001,
        ["DPAD_DOWN"] = 0x0002,
        ["DPAD_LEFT"] = 0x0004,
        ["DPAD_RIGHT"] = 0x0008,
        ["START"] = 0x0010,
        ["BACK"] = 0x0020,
        ["LEFT_THUMB_CLICK"] = 0x0040,
        ["RIGHT_THUMB_CLICK"] = 0x0080,
        ["LEFT_BUMPER"] = 0x0100,
        ["RIGHT_BUMPER"] = 0x0200,
        ["GUIDE"] = 0x0400,
        ["A"] = 0x1000,
        ["B"] = 0x2000,
        ["X"] = 0x4000,
        ["Y"] = 0x8000
    };

    public ControllerService(ConfigStore configStore, AppPaths paths)
    {
        _configStore = configStore;
        _paths = paths;
    }

    public void Start()
    {
        if (_thread is not null)
        {
            return;
        }

        _thread = new Thread(Loop)
        {
            IsBackground = true,
            Name = "PTZ Controller Loop"
        };
        _thread.Start();
    }

    public void Stop()
    {
        _cts.Cancel();
        _thread?.Join(1500);
    }

    private void Loop()
    {
        try
        {
            _configStore.EnsureAndLoad();

            var physicalSlotsBefore = GetConnectedSlots();
            _client = new ViGEmClient();
            _controller = _client.CreateXbox360Controller();
            _controller.Connect();

            Thread.Sleep(1000);
            var currentSlots = GetConnectedSlots();
            var newSlot = currentSlots.Except(physicalSlotsBefore).FirstOrDefault(-1);

            var lastModified = File.GetLastWriteTimeUtc(_paths.ConfigPath);
            var config = _configStore.Load();

            var latchedButtons = new HashSet<Xbox360Button>();
            short latchedLx = 0, latchedLy = 0, latchedRx = 0, latchedRy = 0;
            byte latchedLt = 0, latchedRt = 0;

            while (!_cts.IsCancellationRequested)
            {
                try
                {
                    var changed = File.GetLastWriteTimeUtc(_paths.ConfigPath);
                    if (changed > lastModified)
                    {
                        Thread.Sleep(50);
                        config = _configStore.Load();
                        lastModified = changed;
                    }
                }
                catch
                {
                }

                var holdControl = config.HoldControl;
                var modifierPressed = string.IsNullOrWhiteSpace(config.ModifierKey) || KeyboardInput.IsPressed(config.ModifierKey);
                var boostPressed = KeyboardInput.IsPressed(config.BoostKey);
                var keyboardActive = modifierPressed || boostPressed;
                var boostMultiplier = config.BoostMultiplier <= 0 ? 1.0 : config.BoostMultiplier;

                var physical = GetPhysicalGamepadState(newSlot);

                HashSet<Xbox360Button> currentButtons = new();
                byte currentLt = 0;
                byte currentRt = 0;
                short currentLx = 0, currentLy = 0, currentRx = 0, currentRy = 0;

                if (keyboardActive)
                {
                    foreach (var pair in ButtonMap)
                    {
                        if (config.Buttons.TryGetValue(pair.Key, out var mapped) && KeyboardInput.IsPressed(mapped))
                        {
                            currentButtons.Add(pair.Value);
                        }
                    }

                    currentLt = ReadTrigger(config.Triggers, "LEFT_TRIGGER");
                    currentRt = ReadTrigger(config.Triggers, "RIGHT_TRIGGER");

                    currentLx = ReadAxis(config.Joysticks, "LEFT_X_MIN", "LEFT_X_MAX");
                    currentLy = ReadAxis(config.Joysticks, "LEFT_Y_MIN", "LEFT_Y_MAX");
                    currentRx = ReadAxis(config.Joysticks, "RIGHT_X_MIN", "RIGHT_X_MAX");
                    currentRy = ReadAxis(config.Joysticks, "RIGHT_Y_MIN", "RIGHT_Y_MAX");

                    if (holdControl)
                    {
                        if (currentButtons.Count > 0)
                        {
                            latchedButtons.UnionWith(currentButtons);
                        }

                        if (currentLt != 0 || currentRt != 0)
                        {
                            latchedLt = currentLt;
                            latchedRt = currentRt;
                        }

                        if (currentLx != 0 || currentLy != 0)
                        {
                            latchedLx = currentLx;
                            latchedLy = currentLy;
                        }

                        if (currentRx != 0 || currentRy != 0)
                        {
                            latchedRx = currentRx;
                            latchedRy = currentRy;
                        }
                    }
                    else
                    {
                        latchedButtons = currentButtons;
                        latchedLt = currentLt;
                        latchedRt = currentRt;
                        latchedLx = currentLx;
                        latchedLy = currentLy;
                        latchedRx = currentRx;
                        latchedRy = currentRy;
                    }

                    var mult = boostPressed ? boostMultiplier : 1.0;
                    latchedLt = (byte)Math.Clamp((int)(latchedLt * mult), 0, 255);
                    latchedRt = (byte)Math.Clamp((int)(latchedRt * mult), 0, 255);
                    latchedLx = (short)Math.Clamp((int)(latchedLx * mult), short.MinValue, short.MaxValue);
                    latchedLy = (short)Math.Clamp((int)(latchedLy * mult), short.MinValue, short.MaxValue);
                    latchedRx = (short)Math.Clamp((int)(latchedRx * mult), short.MinValue, short.MaxValue);
                    latchedRy = (short)Math.Clamp((int)(latchedRy * mult), short.MinValue, short.MaxValue);
                }
                else
                {
                    latchedButtons.Clear();
                    latchedLt = latchedRt = 0;
                    latchedLx = latchedLy = latchedRx = latchedRy = 0;
                }

                Submit(physical, latchedButtons, latchedLt, latchedRt, latchedLx, latchedLy, latchedRx, latchedRy);
                Thread.Sleep(10);
            }
        }
        catch
        {
            // Keep behavior consistent with the original app: fail silently in loop.
        }
        finally
        {
            lock (_lock)
            {
                if (_controller is not null)
                {
                    _controller.SetButtonState(Xbox360Button.A, false);
                    _controller.SetButtonState(Xbox360Button.B, false);
                    _controller.SetButtonState(Xbox360Button.X, false);
                    _controller.SetButtonState(Xbox360Button.Y, false);
                    _controller.SetSliderValue(Xbox360Slider.LeftTrigger, 0);
                    _controller.SetSliderValue(Xbox360Slider.RightTrigger, 0);
                    _controller.SetAxisValue(Xbox360Axis.LeftThumbX, 0);
                    _controller.SetAxisValue(Xbox360Axis.LeftThumbY, 0);
                    _controller.SetAxisValue(Xbox360Axis.RightThumbX, 0);
                    _controller.SetAxisValue(Xbox360Axis.RightThumbY, 0);
                    _controller.SubmitReport();
                    _controller.Disconnect();
                    _controller = null;
                }

                _client?.Dispose();
                _client = null;
            }
        }
    }

    private void Submit(NativeMethods.XInputGamepad? physical, HashSet<Xbox360Button> keyboardButtons, byte ltKeyboard, byte rtKeyboard, short lxKeyboard, short lyKeyboard, short rxKeyboard, short ryKeyboard)
    {
        lock (_lock)
        {
            if (_controller is null)
            {
                return;
            }

            foreach (var pair in ButtonMap)
            {
                var keyboardPressed = keyboardButtons.Contains(pair.Value);
                var physicalPressed = physical.HasValue && PhysicalButtonMask.TryGetValue(pair.Key, out var mask) && (physical.Value.wButtons & mask) != 0;
                _controller.SetButtonState(pair.Value, keyboardPressed || physicalPressed);
            }

            var ltPhysical = physical?.bLeftTrigger ?? 0;
            var rtPhysical = physical?.bRightTrigger ?? 0;
            _controller.SetSliderValue(Xbox360Slider.LeftTrigger, Math.Max(ltKeyboard, ltPhysical));
            _controller.SetSliderValue(Xbox360Slider.RightTrigger, Math.Max(rtKeyboard, rtPhysical));

            var finalLx = (short)Math.Clamp((physical?.sThumbLX ?? 0) + lxKeyboard, short.MinValue, short.MaxValue);
            var finalLy = (short)Math.Clamp((physical?.sThumbLY ?? 0) + lyKeyboard, short.MinValue, short.MaxValue);
            var finalRx = (short)Math.Clamp((physical?.sThumbRX ?? 0) + rxKeyboard, short.MinValue, short.MaxValue);
            var finalRy = (short)Math.Clamp((physical?.sThumbRY ?? 0) + ryKeyboard, short.MinValue, short.MaxValue);

            _controller.SetAxisValue(Xbox360Axis.LeftThumbX, finalLx);
            _controller.SetAxisValue(Xbox360Axis.LeftThumbY, finalLy);
            _controller.SetAxisValue(Xbox360Axis.RightThumbX, finalRx);
            _controller.SetAxisValue(Xbox360Axis.RightThumbY, finalRy);
            _controller.SubmitReport();
        }
    }

    private static byte ReadTrigger(Dictionary<string, AxisBinding> map, string name)
    {
        if (!map.TryGetValue(name, out var binding))
        {
            return 0;
        }

        if (!KeyboardInput.IsPressed(binding.Keys))
        {
            return 0;
        }

        return (byte)ParsePercentage(binding.Value, 255);
    }

    private static short ReadAxis(Dictionary<string, AxisBinding> map, string minName, string maxName)
    {
        if (map.TryGetValue(minName, out var minBinding) && KeyboardInput.IsPressed(minBinding.Keys))
        {
            return (short)ParsePercentage(minBinding.Value, short.MinValue);
        }

        if (map.TryGetValue(maxName, out var maxBinding) && KeyboardInput.IsPressed(maxBinding.Keys))
        {
            return (short)ParsePercentage(maxBinding.Value, short.MaxValue);
        }

        return 0;
    }

    private static int ParsePercentage(string? text, int rawLimit)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return rawLimit;
        }

        var normalized = text.Replace("%", string.Empty, StringComparison.OrdinalIgnoreCase).Trim();
        if (!double.TryParse(normalized, out var pct))
        {
            return rawLimit;
        }

        pct = Math.Clamp(pct, 0d, 100d);
        return (int)((pct / 100.0d) * rawLimit);
    }

    private static HashSet<int> GetConnectedSlots()
    {
        var slots = new HashSet<int>();
        for (var i = 0; i < 4; i++)
        {
            if (NativeMethods.TryGetXInputState(i, out _))
            {
                slots.Add(i);
            }
        }

        return slots;
    }

    private static NativeMethods.XInputGamepad? GetPhysicalGamepadState(int excludedSlot)
    {
        for (var i = 0; i < 4; i++)
        {
            if (i == excludedSlot)
            {
                continue;
            }

            if (NativeMethods.TryGetXInputState(i, out var state))
            {
                return state.Gamepad;
            }
        }

        return null;
    }

    public void Dispose()
    {
        Stop();
        _cts.Dispose();
    }
}
