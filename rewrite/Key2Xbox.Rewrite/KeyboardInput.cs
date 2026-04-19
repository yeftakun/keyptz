using System.Windows.Forms;

namespace KeyPTZ.Desktop;

public static class KeyboardInput
{
    private static readonly Dictionary<string, Keys> NameToKey = BuildMap();

    public static bool IsPressed(string? keyText)
    {
        if (string.IsNullOrWhiteSpace(keyText))
        {
            return false;
        }

        var keys = ParseKeys(keyText);
        return keys.Any(IsPressed);
    }

    public static bool IsPressed(IEnumerable<string>? keyTexts)
    {
        if (keyTexts is null)
        {
            return false;
        }

        foreach (var key in keyTexts)
        {
            if (IsPressed(key))
            {
                return true;
            }
        }

        return false;
    }

    public static List<string> SplitKeys(string text)
    {
        return text.Split(',')
            .Select(k => k.Trim())
            .Where(k => !string.IsNullOrWhiteSpace(k))
            .ToList();
    }

    public static string ToConfigKeyName(Keys key)
    {
        return key switch
        {
            Keys.OemMinus or Keys.Subtract => "-",
            Keys.Oemplus or Keys.Add => "+",
            Keys.Return => "enter",
            Keys.Escape => "esc",
            Keys.ControlKey => "ctrl",
            Keys.Menu => "alt",
            Keys.ShiftKey => "shift",
            _ => key.ToString().ToLowerInvariant()
        };
    }

    private static IEnumerable<Keys> ParseKeys(string keyText)
    {
        foreach (var token in keyText.Split(','))
        {
            var normalized = token.Trim().ToLowerInvariant();
            if (string.IsNullOrEmpty(normalized))
            {
                continue;
            }

            if (NameToKey.TryGetValue(normalized, out var key))
            {
                yield return key;

                // Accept both top-row and numpad variants for +/- shortcuts.
                if (key == Keys.Oemplus)
                {
                    yield return Keys.Add;
                }
                else if (key == Keys.OemMinus)
                {
                    yield return Keys.Subtract;
                }

                continue;
            }

            if (normalized.Length == 1)
            {
                var c = normalized[0];
                if (char.IsLetter(c))
                {
                    yield return (Keys)Enum.Parse(typeof(Keys), char.ToUpperInvariant(c).ToString());
                    continue;
                }

                if (char.IsDigit(c))
                {
                    yield return Keys.D0 + (c - '0');
                    yield return Keys.NumPad0 + (c - '0');
                }
            }
        }
    }

    private static bool IsPressed(Keys key)
    {
        var state = NativeMethods.GetAsyncKeyState((int)key);
        return (state & 0x8000) != 0;
    }

    private static Dictionary<string, Keys> BuildMap()
    {
        return new Dictionary<string, Keys>(StringComparer.OrdinalIgnoreCase)
        {
            ["enter"] = Keys.Return,
            ["return"] = Keys.Return,
            ["tab"] = Keys.Tab,
            ["space"] = Keys.Space,
            ["esc"] = Keys.Escape,
            ["escape"] = Keys.Escape,
            ["left"] = Keys.Left,
            ["right"] = Keys.Right,
            ["up"] = Keys.Up,
            ["down"] = Keys.Down,
            ["ctrl"] = Keys.ControlKey,
            ["control"] = Keys.ControlKey,
            ["shift"] = Keys.ShiftKey,
            ["alt"] = Keys.Menu,
            ["+"] = Keys.Oemplus,
            ["-"] = Keys.OemMinus,
            ["0"] = Keys.D0,
            ["1"] = Keys.D1,
            ["2"] = Keys.D2,
            ["3"] = Keys.D3,
            ["4"] = Keys.D4,
            ["5"] = Keys.D5,
            ["6"] = Keys.D6,
            ["7"] = Keys.D7,
            ["8"] = Keys.D8,
            ["9"] = Keys.D9,
            ["numpad0"] = Keys.NumPad0,
            ["numpad1"] = Keys.NumPad1,
            ["numpad2"] = Keys.NumPad2,
            ["numpad3"] = Keys.NumPad3,
            ["numpad4"] = Keys.NumPad4,
            ["numpad5"] = Keys.NumPad5,
            ["numpad6"] = Keys.NumPad6,
            ["numpad7"] = Keys.NumPad7,
            ["numpad8"] = Keys.NumPad8,
            ["numpad9"] = Keys.NumPad9,
            ["add"] = Keys.Add,
            ["subtract"] = Keys.Subtract,
            ["multiply"] = Keys.Multiply,
            ["divide"] = Keys.Divide,
            ["decimal"] = Keys.Decimal
        };
    }
}
