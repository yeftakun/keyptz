using System.Diagnostics;
using System.Drawing;
using System.Windows.Forms;

namespace Key2Xbox.Rewrite;

public sealed class TrayApplicationContext : ApplicationContext
{
    private readonly NotifyIcon _trayIcon;
    private readonly ControllerService _controllerService;
    private readonly ConfigStore _store;
    private readonly AppPaths _paths;

    private bool _isConfigOpen;

    public TrayApplicationContext(AppPaths paths)
    {
        _paths = paths;
        _store = new ConfigStore(_paths);
        _controllerService = new ControllerService(_store, _paths);

        _trayIcon = new NotifyIcon
        {
            Icon = CreateTrayIcon(),
            Visible = true,
            Text = "vMix PTZ Controller"
        };

        var menu = new ContextMenuStrip();
        menu.Items.Add("Config", null, (_, _) => OpenConfig());
        menu.Items.Add("GitHub", null, (_, _) => OpenGithub());
        menu.Items.Add("Exit", null, (_, _) => ExitApp());
        _trayIcon.ContextMenuStrip = menu;

        ShowStartupAlert();
        _controllerService.Start();
    }

    private void OpenConfig()
    {
        if (_isConfigOpen)
        {
            return;
        }

        try
        {
            _isConfigOpen = true;
            using var form = new ConfigEditorForm(_store, _paths);
            form.ShowDialog();
        }
        finally
        {
            _isConfigOpen = false;
        }
    }

    private static void OpenGithub()
    {
        Process.Start(new ProcessStartInfo
        {
            FileName = "https://github.com/yeftakun/keyptz",
            UseShellExecute = true
        });
    }

    private void ExitApp()
    {
        _controllerService.Stop();
        _trayIcon.Visible = false;
        _trayIcon.Dispose();
        ExitThread();
    }

    protected override void ExitThreadCore()
    {
        _controllerService.Dispose();
        base.ExitThreadCore();
    }

    private static void ShowStartupAlert()
    {
        MessageBox.Show("KeyPTZ berjalan di Background", "Sukses", MessageBoxButtons.OK, MessageBoxIcon.Information);
    }

    private static Icon CreateTrayIcon()
    {
        using var bmp = new Bitmap(64, 64);
        using (var g = Graphics.FromImage(bmp))
        {
            g.Clear(Color.Black);
            using var brush = new SolidBrush(Color.Green);
            g.FillEllipse(brush, 10, 10, 44, 44);
        }

        return Icon.FromHandle(bmp.GetHicon());
    }
}
