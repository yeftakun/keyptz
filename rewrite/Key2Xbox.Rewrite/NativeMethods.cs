using System.Runtime.InteropServices;

namespace KeyPTZ.Desktop;

internal static class NativeMethods
{
    [DllImport("user32.dll")]
    internal static extern short GetAsyncKeyState(int vKey);

    [StructLayout(LayoutKind.Sequential)]
    internal struct XInputGamepad
    {
        public ushort wButtons;
        public byte bLeftTrigger;
        public byte bRightTrigger;
        public short sThumbLX;
        public short sThumbLY;
        public short sThumbRX;
        public short sThumbRY;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct XInputState
    {
        public uint dwPacketNumber;
        public XInputGamepad Gamepad;
    }

    [DllImport("xinput1_4.dll", EntryPoint = "XInputGetState")]
    private static extern uint XInputGetState14(int dwUserIndex, out XInputState pState);

    [DllImport("xinput9_1_0.dll", EntryPoint = "XInputGetState")]
    private static extern uint XInputGetState910(int dwUserIndex, out XInputState pState);

    [DllImport("xinput1_3.dll", EntryPoint = "XInputGetState")]
    private static extern uint XInputGetState13(int dwUserIndex, out XInputState pState);

    internal static bool TryGetXInputState(int userIndex, out XInputState state)
    {
        state = default;

        try
        {
            if (XInputGetState14(userIndex, out state) == 0)
            {
                return true;
            }

            return false;
        }
        catch (DllNotFoundException)
        {
        }
        catch (EntryPointNotFoundException)
        {
        }

        try
        {
            if (XInputGetState910(userIndex, out state) == 0)
            {
                return true;
            }

            return false;
        }
        catch (DllNotFoundException)
        {
        }
        catch (EntryPointNotFoundException)
        {
        }

        try
        {
            if (XInputGetState13(userIndex, out state) == 0)
            {
                return true;
            }

            return false;
        }
        catch (DllNotFoundException)
        {
            return false;
        }
        catch (EntryPointNotFoundException)
        {
            return false;
        }
    }
}
