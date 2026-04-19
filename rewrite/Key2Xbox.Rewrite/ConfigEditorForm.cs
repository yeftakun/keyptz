using System.Diagnostics;
using System.Drawing;
using System.Windows.Forms;

namespace Key2Xbox.Rewrite;

public sealed class ConfigEditorForm : Form
{
    private readonly ConfigStore _store;
    private readonly AppPaths _paths;
    private AppConfig _config;

    private readonly CheckBox _holdControl = new() { AutoSize = true, Text = "Enable Hold/Cruise Control" };
    private readonly TextBox _modifier = new() { ReadOnly = true, Width = 170 };
    private readonly TextBox _boost = new() { ReadOnly = true, Width = 170 };
    private readonly TextBox _multiplier = new() { Width = 170 };

    private readonly Dictionary<string, TextBox> _buttonBoxes = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, (TextBox keys, TextBox value)> _analogBoxes = new(StringComparer.OrdinalIgnoreCase);
    private readonly List<(TextBox box, bool isList)> _mappingBoxes = new();

    private readonly Label _dupWarning = new()
    {
        Text = "Ada tombol xbox yang memakai keyboard yang sama!",
        ForeColor = Color.Red,
        Font = new Font("Segoe UI", 9, FontStyle.Bold),
        Visible = false,
        AutoSize = true
    };

    private readonly ListBox _profiles = new() { Height = 180 };
    private readonly TextBox _newProfileName = new();

    private TextBox? _captureTarget;
    private string _captureOld = string.Empty;
    private readonly System.Windows.Forms.Timer _captureTimer = new() { Interval = 5000 };

    private static readonly string[] ButtonOrder =
    {
        "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT",
        "START", "BACK", "LEFT_THUMB_CLICK", "RIGHT_THUMB_CLICK",
        "LEFT_BUMPER", "RIGHT_BUMPER", "GUIDE", "A", "B", "X", "Y"
    };

    private static readonly string[] AnalogOrder =
    {
        "LEFT_X_MIN", "LEFT_X_MAX", "LEFT_Y_MIN", "LEFT_Y_MAX",
        "RIGHT_X_MIN", "RIGHT_X_MAX", "RIGHT_Y_MIN", "RIGHT_Y_MAX",
        "LEFT_TRIGGER", "RIGHT_TRIGGER"
    };

    public ConfigEditorForm(ConfigStore store, AppPaths paths)
    {
        _store = store;
        _paths = paths;
        _config = _store.EnsureAndLoad();

        Text = "KeyPTZ - Config & Profile Editor";
        Width = 700;
        Height = 760;
        FormBorderStyle = FormBorderStyle.FixedSingle;
        MaximizeBox = false;
        MinimizeBox = false;
        TopMost = true;
        StartPosition = FormStartPosition.CenterScreen;
        KeyPreview = true;

        BuildLayout();
        ApplyConfigToControls(_config);

        KeyDown += OnCaptureKeyDown;
        _captureTimer.Tick += (_, _) => EndCaptureByTimeout();
    }

    private void BuildLayout()
    {
        var root = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 1,
            RowCount = 3,
            Padding = new Padding(10)
        };
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));

        var tabs = new TabControl { Dock = DockStyle.Fill };
        tabs.TabPages.Add(CreateGeneralTab());
        tabs.TabPages.Add(CreateButtonsTab());
        tabs.TabPages.Add(CreateAnalogTab());
        tabs.TabPages.Add(CreateProfilesTab());

        var buttonPanel = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill,
            FlowDirection = FlowDirection.RightToLeft,
            AutoSize = true,
            WrapContents = false
        };

        var saveButton = new Button { Text = "Save & Apply (Active Config)", Width = 220, Height = 32 };
        saveButton.Click += (_, _) => SaveAndClose();
        buttonPanel.Controls.Add(saveButton);

        root.Controls.Add(tabs, 0, 0);
        root.Controls.Add(_dupWarning, 0, 1);
        root.Controls.Add(buttonPanel, 0, 2);

        Controls.Add(root);
    }

    private TabPage CreateGeneralTab()
    {
        var tab = new TabPage("General");
        var panel = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            Padding = new Padding(10),
            ColumnCount = 3,
            AutoSize = true
        };
        panel.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 190));
        panel.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 250));
        panel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));

        panel.Controls.Add(_holdControl, 0, 0);
        panel.SetColumnSpan(_holdControl, 3);

        panel.Controls.Add(new Label { Text = "Modifier (Kopling) Key:", AutoSize = true }, 0, 1);
        panel.Controls.Add(WrapCaptureButtons(_modifier), 1, 1);

        panel.Controls.Add(new Label { Text = "Boost (Turbo) Key:", AutoSize = true }, 0, 2);
        panel.Controls.Add(WrapCaptureButtons(_boost), 1, 2);

        panel.Controls.Add(new Label { Text = "Boost Multiplier (e.g. 1.5):", AutoSize = true }, 0, 3);
        panel.Controls.Add(_multiplier, 1, 3);

        tab.Controls.Add(panel);
        return tab;
    }

    private TabPage CreateButtonsTab()
    {
        var tab = new TabPage("Buttons");
        var panel = new TableLayoutPanel
        {
            Dock = DockStyle.Top,
            AutoSize = true,
            Padding = new Padding(10),
            ColumnCount = 3
        };

        panel.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 180));
        panel.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 290));
        panel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));

        var row = 0;
        foreach (var button in ButtonOrder)
        {
            panel.Controls.Add(new Label { Text = button, AutoSize = true }, 0, row);
            var box = new TextBox { Width = 190, ReadOnly = true };
            box.TextChanged += (_, _) => CheckDuplicates();
            _buttonBoxes[button] = box;
            _mappingBoxes.Add((box, false));

            panel.Controls.Add(WrapCaptureButtons(box), 1, row);
            row++;
        }

        var scroll = new Panel { Dock = DockStyle.Fill, AutoScroll = true };
        scroll.Controls.Add(panel);
        tab.Controls.Add(scroll);
        return tab;
    }

    private TabPage CreateAnalogTab()
    {
        var tab = new TabPage("Analog & Triggers");
        var panel = new TableLayoutPanel
        {
            Dock = DockStyle.Top,
            AutoSize = true,
            Padding = new Padding(10),
            ColumnCount = 3
        };

        panel.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 180));
        panel.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 330));
        panel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));

        panel.Controls.Add(new Label { Text = "AXIS / TRIGGER", Font = new Font("Segoe UI", 9, FontStyle.Bold), AutoSize = true }, 0, 0);
        panel.Controls.Add(new Label { Text = "KEYS MAP", Font = new Font("Segoe UI", 9, FontStyle.Bold), AutoSize = true }, 1, 0);
        panel.Controls.Add(new Label { Text = "VALUE %", Font = new Font("Segoe UI", 9, FontStyle.Bold), AutoSize = true }, 2, 0);

        var row = 1;
        foreach (var axis in AnalogOrder)
        {
            panel.Controls.Add(new Label { Text = axis, AutoSize = true }, 0, row);

            var keyBox = new TextBox { Width = 160, ReadOnly = true };
            keyBox.TextChanged += (_, _) => CheckDuplicates();
            _mappingBoxes.Add((keyBox, true));

            var valBox = new TextBox { Width = 80 };
            valBox.KeyPress += (_, e) =>
            {
                if (!char.IsControl(e.KeyChar) && !char.IsDigit(e.KeyChar) && e.KeyChar != '.' && e.KeyChar != '%')
                {
                    e.Handled = true;
                }
            };

            _analogBoxes[axis] = (keyBox, valBox);
            panel.Controls.Add(WrapCaptureButtons(keyBox), 1, row);
            panel.Controls.Add(valBox, 2, row);
            row++;
        }

        var scroll = new Panel { Dock = DockStyle.Fill, AutoScroll = true };
        scroll.Controls.Add(panel);
        tab.Controls.Add(scroll);
        return tab;
    }

    private TabPage CreateProfilesTab()
    {
        var tab = new TabPage("Profiles");
        var panel = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            Padding = new Padding(10),
            RowCount = 8,
            ColumnCount = 1
        };

        var loadDefault = new Button { Text = "Load Default Profile (Reset)", Dock = DockStyle.Top };
        loadDefault.Click += (_, _) =>
        {
            ApplyConfigToControls(AppConfig.CreateDefault());
            MessageBox.Show("Default profile telah dimuat ke editor. Klik Save & Apply untuk mengaktifkan.", "Dimuat", MessageBoxButtons.OK, MessageBoxIcon.Information);
        };

        var refresh = new Button { Text = "Refresh Profile List", Dock = DockStyle.Top };
        refresh.Click += (_, _) => RefreshProfiles();

        var loadSelected = new Button { Text = "Load Selected Profile to Editor", Dock = DockStyle.Top };
        loadSelected.Click += (_, _) => LoadSelectedProfile();

        var deleteSelected = new Button { Text = "Delete Selected Profile", Dock = DockStyle.Top };
        deleteSelected.Click += (_, _) => DeleteSelectedProfile();

        var saveNew = new Button { Text = "Save As New Profile", Dock = DockStyle.Top };
        saveNew.Click += (_, _) => SaveAsNewProfile();

        panel.Controls.Add(loadDefault, 0, 0);
        panel.Controls.Add(refresh, 0, 1);
        panel.Controls.Add(new Label { Text = "Available Profiles:", AutoSize = true, Font = new Font("Segoe UI", 10, FontStyle.Bold) }, 0, 2);
        panel.Controls.Add(_profiles, 0, 3);
        panel.Controls.Add(loadSelected, 0, 4);
        panel.Controls.Add(deleteSelected, 0, 5);
        panel.Controls.Add(new Label { Text = "Save Current Editor as New Profile:", AutoSize = true }, 0, 6);
        panel.Controls.Add(_newProfileName, 0, 7);
        panel.Controls.Add(saveNew, 0, 8);

        tab.Controls.Add(panel);

        RefreshProfiles();
        return tab;
    }

    private Control WrapCaptureButtons(TextBox box)
    {
        var panel = new FlowLayoutPanel
        {
            AutoSize = true,
            FlowDirection = FlowDirection.LeftToRight,
            WrapContents = false
        };

        var insert = new Button { Text = "Insert", Width = 60 };
        insert.Click += (_, _) => BeginCapture(box);

        panel.Controls.Add(box);
        panel.Controls.Add(insert);

        var clear = new Button { Text = "X", Width = 30 };
        clear.Click += (_, _) =>
        {
            box.Text = string.Empty;
            CheckDuplicates();
        };
        panel.Controls.Add(clear);

        return panel;
    }

    private void BeginCapture(TextBox target)
    {
        CancelCapture();
        _captureTarget = target;
        _captureOld = target.Text;
        target.Text = "< Menunggu 5d... >";
        _captureTimer.Start();
    }

    private void EndCaptureByTimeout()
    {
        _captureTimer.Stop();
        if (_captureTarget is null)
        {
            return;
        }

        _captureTarget.Text = _captureOld;
        _captureTarget = null;
        MessageBox.Show("Waktu habis! Tidak ada tombol yang ditekan.", "Timeout", MessageBoxButtons.OK, MessageBoxIcon.Information);
        CheckDuplicates();
    }

    private void CancelCapture()
    {
        _captureTimer.Stop();
        if (_captureTarget is not null)
        {
            _captureTarget.Text = _captureOld;
            _captureTarget = null;
        }
    }

    private void OnCaptureKeyDown(object? sender, KeyEventArgs e)
    {
        if (_captureTarget is null)
        {
            return;
        }

        e.SuppressKeyPress = true;
        _captureTimer.Stop();

        if (e.KeyCode == Keys.Escape)
        {
            _captureTarget.Text = _captureOld;
            _captureTarget = null;
            CheckDuplicates();
            return;
        }

        var keyName = KeyboardInput.ToConfigKeyName(e.KeyCode);
        _captureTarget.Text = keyName;

        _captureTarget = null;
        CheckDuplicates();
    }

    private void CheckDuplicates()
    {
        var keyCount = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);

        foreach (var (box, isList) in _mappingBoxes)
        {
            var value = box.Text.Trim();
            if (string.IsNullOrWhiteSpace(value) || value == "< Menunggu 5d... >")
            {
                continue;
            }

            var keys = isList ? KeyboardInput.SplitKeys(value) : new List<string> { value };
            foreach (var key in keys)
            {
                keyCount[key] = keyCount.TryGetValue(key, out var count) ? count + 1 : 1;
            }
        }

        var hasDuplicate = false;

        foreach (var (box, isList) in _mappingBoxes)
        {
            var value = box.Text.Trim();
            var duplicated = false;

            if (!string.IsNullOrWhiteSpace(value) && value != "< Menunggu 5d... >")
            {
                var keys = isList ? KeyboardInput.SplitKeys(value) : new List<string> { value };
                duplicated = keys.Any(k => keyCount.TryGetValue(k, out var count) && count > 1);
            }

            box.BackColor = duplicated ? Color.MistyRose : Color.White;
            box.ForeColor = duplicated ? Color.DarkRed : Color.Black;
            hasDuplicate = hasDuplicate || duplicated;
        }

        _dupWarning.Visible = hasDuplicate;
    }

    private void ApplyConfigToControls(AppConfig config)
    {
        _config = config;
        _holdControl.Checked = config.HoldControl;
        _modifier.Text = config.ModifierKey ?? string.Empty;
        _boost.Text = config.BoostKey ?? string.Empty;
        _multiplier.Text = config.BoostMultiplier.ToString("0.###");

        foreach (var button in ButtonOrder)
        {
            _buttonBoxes[button].Text = config.Buttons.TryGetValue(button, out var key) ? key : string.Empty;
        }

        foreach (var axis in AnalogOrder)
        {
            AxisBinding source;
            if (axis.Contains("TRIGGER", StringComparison.OrdinalIgnoreCase))
            {
                source = config.Triggers.TryGetValue(axis, out var v) ? v : new AxisBinding();
            }
            else
            {
                source = config.Joysticks.TryGetValue(axis, out var v) ? v : new AxisBinding();
            }

            _analogBoxes[axis].keys.Text = string.Join(", ", source.Keys);
            _analogBoxes[axis].value.Text = source.Value;
        }

        CheckDuplicates();
    }

    private AppConfig CollectConfigFromControls()
    {
        var cfg = AppConfig.CreateDefault();
        cfg.HoldControl = _holdControl.Checked;
        cfg.ModifierKey = _modifier.Text.Trim();
        cfg.BoostKey = _boost.Text.Trim();

        if (double.TryParse(_multiplier.Text.Trim(), out var mult))
        {
            cfg.BoostMultiplier = mult;
        }

        foreach (var button in ButtonOrder)
        {
            cfg.Buttons[button] = _buttonBoxes[button].Text.Trim();
        }

        foreach (var axis in AnalogOrder)
        {
            var keys = KeyboardInput.SplitKeys(_analogBoxes[axis].keys.Text);
            if (keys.Count == 0)
            {
                keys.Add(string.Empty);
            }

            var binding = new AxisBinding
            {
                Keys = keys,
                Value = _analogBoxes[axis].value.Text.Trim()
            };

            if (axis.Contains("TRIGGER", StringComparison.OrdinalIgnoreCase))
            {
                cfg.Triggers[axis] = binding;
            }
            else
            {
                cfg.Joysticks[axis] = binding;
            }
        }

        return cfg;
    }

    private void SaveAndClose()
    {
        CancelCapture();
        var cfg = CollectConfigFromControls();
        _store.Save(cfg);
        MessageBox.Show("Config Active berhasil diperbarui!\n(Hot-Reload menyala)", "Tersimpan", MessageBoxButtons.OK, MessageBoxIcon.Information);
        DialogResult = DialogResult.OK;
        Close();
    }

    private void RefreshProfiles()
    {
        Directory.CreateDirectory(_paths.ProfileDirectory);
        _profiles.Items.Clear();
        foreach (var file in Directory.GetFiles(_paths.ProfileDirectory, "*.json"))
        {
            _profiles.Items.Add(Path.GetFileName(file));
        }
    }

    private void LoadSelectedProfile()
    {
        if (_profiles.SelectedItem is null)
        {
            MessageBox.Show("Pilih profile dari daftar terlebih dahulu!", "Pilih Profile", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        var profileName = _profiles.SelectedItem.ToString() ?? string.Empty;
        var path = Path.Combine(_paths.ProfileDirectory, profileName);
        var cfg = _store.LoadProfile(path);
        ApplyConfigToControls(cfg);
        MessageBox.Show($"'{profileName}' telah dimuat ke editor. Klik Save & Apply untuk mengaktifkannya.", "Dimuat", MessageBoxButtons.OK, MessageBoxIcon.Information);
    }

    private void SaveAsNewProfile()
    {
        var name = _newProfileName.Text.Trim();
        if (string.IsNullOrWhiteSpace(name))
        {
            MessageBox.Show("Masukkan nama profile baru!", "Nama Kosong", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        if (string.Equals(name, "default", StringComparison.OrdinalIgnoreCase) || string.Equals(name, "default.json", StringComparison.OrdinalIgnoreCase))
        {
            MessageBox.Show("Nama 'Default' dilindungi dan tidak bisa ditimpa. Gunakan nama lain.", "Ditolak", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        if (!name.EndsWith(".json", StringComparison.OrdinalIgnoreCase))
        {
            name += ".json";
        }

        var path = Path.Combine(_paths.ProfileDirectory, name);
        _store.SaveProfile(path, CollectConfigFromControls());
        _newProfileName.Text = string.Empty;
        RefreshProfiles();
        MessageBox.Show($"Profile disimpan sebagai '{name}'.", "Tersimpan", MessageBoxButtons.OK, MessageBoxIcon.Information);
    }

    private void DeleteSelectedProfile()
    {
        if (_profiles.SelectedItem is null)
        {
            return;
        }

        var profileName = _profiles.SelectedItem.ToString() ?? string.Empty;
        if (MessageBox.Show($"Hapus profile '{profileName}'?", "Konfirmasi", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes)
        {
            return;
        }

        var path = Path.Combine(_paths.ProfileDirectory, profileName);
        if (File.Exists(path))
        {
            File.Delete(path);
        }

        RefreshProfiles();
    }
}
