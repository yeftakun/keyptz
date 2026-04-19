using System.Threading;
using System.Windows.Forms;

namespace Key2Xbox.Rewrite;

internal static class Program
{
    private const string MutexName = "KeyPTZ_vMix_Controller_Mutex_12345";

    [STAThread]
    private static void Main()
    {
        using var mutex = new Mutex(initiallyOwned: true, name: MutexName, createdNew: out var createdNew);
        if (!createdNew)
        {
            MessageBox.Show("KeyPTZ sebelumnya sudah berjalan!", "Peringatan", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        ApplicationConfiguration.Initialize();
        var paths = new AppPaths(AppContext.BaseDirectory);
        Application.Run(new TrayApplicationContext(paths));
    }
}