using Newtonsoft.Json;

namespace Key2Xbox.Rewrite;

public sealed class AppConfig
{
    [JsonProperty("hold_control")]
    public bool HoldControl { get; set; }

    [JsonProperty("modifier_key")]
    public string ModifierKey { get; set; } = "numpad0";

    [JsonProperty("boost_key")]
    public string BoostKey { get; set; } = "numpad1";

    [JsonProperty("boost_multiplier")]
    public double BoostMultiplier { get; set; } = 1.3;

    [JsonProperty("buttons")]
    public Dictionary<string, string> Buttons { get; set; } = new(StringComparer.OrdinalIgnoreCase);

    [JsonProperty("triggers")]
    public Dictionary<string, AxisBinding> Triggers { get; set; } = new(StringComparer.OrdinalIgnoreCase);

    [JsonProperty("joysticks")]
    public Dictionary<string, AxisBinding> Joysticks { get; set; } = new(StringComparer.OrdinalIgnoreCase);

    public static AppConfig CreateDefault()
    {
        return new AppConfig
        {
            HoldControl = false,
            ModifierKey = "numpad0",
            BoostKey = "numpad1",
            BoostMultiplier = 1.3,
            Buttons = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["DPAD_UP"] = "",
                ["DPAD_DOWN"] = "",
                ["DPAD_LEFT"] = "",
                ["DPAD_RIGHT"] = "",
                ["START"] = "",
                ["BACK"] = "",
                ["LEFT_THUMB_CLICK"] = "",
                ["RIGHT_THUMB_CLICK"] = "",
                ["LEFT_BUMPER"] = "",
                ["RIGHT_BUMPER"] = "",
                ["GUIDE"] = "",
                ["A"] = "multiply",
                ["B"] = "",
                ["X"] = "",
                ["Y"] = ""
            },
            Triggers = new Dictionary<string, AxisBinding>(StringComparer.OrdinalIgnoreCase)
            {
                ["LEFT_TRIGGER"] = new AxisBinding { Keys = new List<string> { "" }, Value = "26" },
                ["RIGHT_TRIGGER"] = new AxisBinding { Keys = new List<string> { "" }, Value = "26" }
            },
            Joysticks = new Dictionary<string, AxisBinding>(StringComparer.OrdinalIgnoreCase)
            {
                ["LEFT_X_MIN"] = new AxisBinding { Keys = new List<string> { "numpad4" }, Value = "26" },
                ["LEFT_X_MAX"] = new AxisBinding { Keys = new List<string> { "numpad6" }, Value = "26" },
                ["LEFT_Y_MIN"] = new AxisBinding { Keys = new List<string> { "numpad2" }, Value = "26" },
                ["LEFT_Y_MAX"] = new AxisBinding { Keys = new List<string> { "numpad8" }, Value = "26" },
                ["RIGHT_X_MIN"] = new AxisBinding { Keys = new List<string> { "" }, Value = "26" },
                ["RIGHT_X_MAX"] = new AxisBinding { Keys = new List<string> { "" }, Value = "26" },
                ["RIGHT_Y_MIN"] = new AxisBinding { Keys = new List<string> { "-" }, Value = "50" },
                ["RIGHT_Y_MAX"] = new AxisBinding { Keys = new List<string> { "+" }, Value = "50" }
            }
        };
    }
}

public sealed class AxisBinding
{
    [JsonProperty("keys")]
    public List<string> Keys { get; set; } = new() { "" };

    [JsonProperty("value")]
    public string Value { get; set; } = "26";
}

public sealed class AppPaths
{
    public AppPaths(string baseDirectory)
    {
        BaseDirectory = baseDirectory;
        ConfigPath = Path.Combine(BaseDirectory, "config.json");
        ProfileDirectory = Path.Combine(BaseDirectory, "profile");
    }

    public string BaseDirectory { get; }
    public string ConfigPath { get; }
    public string ProfileDirectory { get; }
}

public sealed class ConfigStore
{
    private readonly AppPaths _paths;
    private readonly JsonSerializerSettings _jsonSettings = new()
    {
        Formatting = Formatting.Indented,
        NullValueHandling = NullValueHandling.Ignore
    };

    public ConfigStore(AppPaths paths)
    {
        _paths = paths;
        Directory.CreateDirectory(_paths.ProfileDirectory);
    }

    public AppConfig EnsureAndLoad()
    {
        if (!File.Exists(_paths.ConfigPath))
        {
            var defaultConfig = AppConfig.CreateDefault();
            Save(defaultConfig);
            return defaultConfig;
        }

        return Load();
    }

    public AppConfig Load()
    {
        var text = File.ReadAllText(_paths.ConfigPath);
        var cfg = JsonConvert.DeserializeObject<AppConfig>(text) ?? AppConfig.CreateDefault();
        Normalize(cfg);
        return cfg;
    }

    public void Save(AppConfig config)
    {
        Normalize(config);
        var text = JsonConvert.SerializeObject(config, _jsonSettings);
        File.WriteAllText(_paths.ConfigPath, text);
    }

    public AppConfig LoadProfile(string profileFile)
    {
        var text = File.ReadAllText(profileFile);
        var cfg = JsonConvert.DeserializeObject<AppConfig>(text) ?? AppConfig.CreateDefault();
        Normalize(cfg);
        return cfg;
    }

    public void SaveProfile(string profileFile, AppConfig config)
    {
        Normalize(config);
        var text = JsonConvert.SerializeObject(config, _jsonSettings);
        File.WriteAllText(profileFile, text);
    }

    private static void Normalize(AppConfig cfg)
    {
        var defaults = AppConfig.CreateDefault();

        foreach (var key in defaults.Buttons.Keys)
        {
            if (!cfg.Buttons.ContainsKey(key))
            {
                cfg.Buttons[key] = defaults.Buttons[key];
            }
        }

        foreach (var key in defaults.Triggers.Keys)
        {
            if (!cfg.Triggers.ContainsKey(key))
            {
                cfg.Triggers[key] = defaults.Triggers[key];
            }
            else if (cfg.Triggers[key].Keys.Count == 0)
            {
                cfg.Triggers[key].Keys = new List<string> { "" };
            }
        }

        foreach (var key in defaults.Joysticks.Keys)
        {
            if (!cfg.Joysticks.ContainsKey(key))
            {
                cfg.Joysticks[key] = defaults.Joysticks[key];
            }
            else if (cfg.Joysticks[key].Keys.Count == 0)
            {
                cfg.Joysticks[key].Keys = new List<string> { "" };
            }
        }
    }
}
