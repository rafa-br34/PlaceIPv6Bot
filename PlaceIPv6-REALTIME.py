import requests
import socket
import random
import numba
import time
import math
import sys
import os
import io
from PIL import Image

from Networking import ICMPv6

c_RootAddress = "2a01:4f8:c012:f8e6" # Canvas base address
c_CanvasURL = "https://ssi.place/canvas.png" # Canvas base URL
c_TargetImage = (len(sys.argv) > 1 and sys.argv[1]) or "image.png" # Target image
c_MaxColorDifference = 4 # The maximum color difference(Used in every comparison). Recommended: 4, 8, or 16
c_ImageCheckWaitTime = 2 # The amount of time to wait before checking the image again if there are no more operations
c_BufferSize = 512 # Socket buffer size(in MB)


g_SharedData = {
    "Run": True,
    "WriteQueue": [],
    "CanvasSize": [512, 512],
}

def LinePrint(*args, sep=' ', end=''):
    ResultString = ""
    for Argument in args:
        ResultString += str(Argument) + sep
    
    PadLen = (os.get_terminal_size()[0] - len(ResultString)) - 1
    Padding = (PadLen > 0 and (' ' * PadLen)) or ''
    print(ResultString, end=Padding + '\r' + end)

g_ProfilerStack = []

def PROFILER_START():
    g_ProfilerStack.append(time.time())

def PROFILER_END():
    return time.time() - g_ProfilerStack.pop()

@numba.jit(nopython=True)
def CompareColor(A, B):
    return math.sqrt((A[0] - B[0]) ** 2 + (A[1] - B[1]) ** 2 + (A[2] - B[2]) ** 2)

def MakeAddress(Size, X, Y, R, G, B, *_):
    return "{Address}:{S:01x}{XXX:03x}:{YYYY:04x}:{RR:02x}:{GG:02x}{BB:02x}".format(
        Address=c_RootAddress,
        S=Size,
        XXX=X, YYYY=Y,
        RR=round(R), GG=round(G), BB=round(B)
    )

@numba.jit(numba.uint32(numba.uint32, numba.uint32), nopython=True)
def FLAG(X, Y):
    return ((Y & 0xFFFF) << 16) | ((X & 0xFFFF) << 0)

def main():
    global g_SharedData
    CanvasSize = g_SharedData["CanvasSize"]

    PROFILER_START()
    OriginalTargetImage = Image.open(c_TargetImage)
    TargetImage = OriginalTargetImage.resize((CanvasSize[0], CanvasSize[1]))
    LinePrint(f"Loaded & Resized Image In {round(PROFILER_END() * 1000)}ms", end='\n')

    SocketObject = socket.socket(socket.AF_INET6, socket.SOCK_RAW, socket.IPPROTO_ICMPV6)
    SocketObject.setblocking(False)
    SocketObject.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, c_BufferSize * (1024 * 1024))
    # SocketObject.setsockopt(socket.SOL_SOCKET, socket.SO_SNDTIMEO, 0) # No Need For It

    try:
        while g_SharedData["Run"]:
            PROFILER_START()
            try:
                CanvasResult = requests.get(c_CanvasURL)
            except KeyboardInterrupt as KBD:
                raise KBD # Pass To Main Loop
            except (BaseException, ConnectionError, ConnectionResetError) as Error:
                print("Failed To Acquire Canvas Image, Exception:", Error)
                continue
            except:
                print("Failed To Acquire Canvas Image, Unknown Exception")
                continue
            finally:
                pass
                
            if CanvasResult.status_code != 200:
                print(f"Failed To Acquire Canvas Image. Status Code {CanvasResult.status_code}")
                time.sleep(3)
                continue

            CanvasImage = Image.open(io.BytesIO(CanvasResult.content))
            TimeImageAcquire = PROFILER_END()

            # Compare Canvas Image With Target Image
            if CanvasImage.size != TargetImage.size:
                print(f"Canvas/Target Size Mismatch, Canvas: {CanvasImage.size} Target: {TargetImage.size}. Resizing...")
                PROFILER_START()
                CanvasSize = CanvasImage.size
                TargetImage = OriginalTargetImage.resize((CanvasSize[0], CanvasSize[1]))
                print(f"Resized Image In {round(PROFILER_END() * 1000)}ms")

            PROFILER_START()
            CPXS = CanvasImage.load() # Canvas Pixels
            TPXS = TargetImage.load() # Target Pixels
            DoneList = []
            Sends = 0
            for X in range(CanvasSize[0]):
                Packet = ICMPv6.MakeEchoPacket(random.randint(0x0000, 0xFFFF), random.randint(0x0000, 0xFFFF), b"")
                for Y in range(CanvasSize[1]):
                    CPX = CPXS[X, Y]
                    TPX = TPXS[X, Y]
                    DIFF00 = CompareColor(TPX, CPX)
                    if not (DIFF00 < c_MaxColorDifference) and (not FLAG(X, Y) in DoneList):
                        DoneList.append(FLAG(X + 0, Y + 0))
                        # Can Fit X/Y/All
                        CFX = (X + 1 < CanvasSize[0])
                        CFY = (Y + 1 < CanvasSize[1])
                        CFA = CFX and CFY

                        DIFF10 = (CFX and CompareColor(TPX, TPXS[X + 1, Y + 0])) or 0
                        DIFF01 = (CFY and CompareColor(TPX, TPXS[X + 0, Y + 1])) or 0
                        DIFF11 = (CFA and CompareColor(TPX, TPXS[X + 1, Y + 1])) or 0

                        if CFA and ((DIFF01 + DIFF10 + DIFF11) < (c_MaxColorDifference * 3)):
                            Address = (MakeAddress(2, X, Y, TPX[0], TPX[1], TPX[2]), 0)
                            DoneList += [FLAG(X + 1, Y + 0), FLAG(X + 0, Y + 1), FLAG(X + 1, Y + 1)]
                        else:
                            Address = (MakeAddress(1, X, Y, TPX[0], TPX[1], TPX[2]), 0)
                        
                        SocketObject.sendto(Packet, Address)
                        Sends += 1

                if X % 2 == 0:
                    DoneList.clear()

            TimeImageProcess = PROFILER_END()
            LinePrint("Image(Acquired In {:.2f}s, Processed In {:.2f}s, {:.2f} Total), {} Pings Sent".format(TimeImageAcquire, TimeImageProcess, TimeImageAcquire + TimeImageProcess, Sends))

            if len(g_SharedData["WriteQueue"]) == 0:
                time.sleep(c_ImageCheckWaitTime)
    except KeyboardInterrupt:
        LinePrint("\nKeyboardInterrupt, Stopping...")
    except BaseException as Error:
        LinePrint("\nMain Thread Exception:", end='\n')
        print(Error)


if __name__ == "__main__":
    main()