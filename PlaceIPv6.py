import threading
import requests
import asyncio
import icmplib
import random
import time
import math
import io
from PIL import Image

c_ConcurrentPings = 5000 # Concurrent pings
c_RootAddress = "2a01:4f8:c012:f8e6" # Canvas base address
c_CanvasURL = "https://ssi.place/canvas.png" # Canvas base URL
c_TargetImage = "image.png" # Target image
c_ChunkSize = c_ConcurrentPings * 2 # The amount of pings to feed icmplib.multiping per iteration
c_MaxColorDifference = 4 # The maximum color difference(Used in every comparison). Recommended: 4, 8, 16
c_Privileged = False # Use on Unix OSes for better speed. Ignored on Windows.
c_DrawMode = "LAST" # In what order pixels will be drawn [SCATTER, FIRST, LAST]

g_SharedData = {
    "Run": True,
    "WriteQueue": [],
    "CanvasSize": [512, 512],
}

def CompareColor(A, B):
    return math.sqrt((A[0] - B[0]) ** 2 + (A[1] - B[1]) ** 2 + (A[2] - B[2]) ** 2) < c_MaxColorDifference
def MakeAddress(Size, X, Y, R, G, B):
    return "{Address}:{S:01x}{XXX:03x}:{YYYY:04x}:{RR:02x}:{GG:02x}{BB:02x}".format(
        Address=c_RootAddress,
        S=Size,
        XXX=X, YYYY=Y,
        RR=round(R), GG=round(G), BB=round(B)
    )
def ICMPWorkerLogic():
    global g_SharedData

    while g_SharedData["Run"]:
        Chunk = []
        WriteQueue = g_SharedData["WriteQueue"]
        for i in range(c_ChunkSize):
            if i >= len(WriteQueue):
                break
            if c_DrawMode == "SCATTER":
                Chunk.append(WriteQueue.pop(random.randint(0, len(WriteQueue) - 1)))
            elif c_DrawMode == "LAST":
                Chunk.append(WriteQueue.pop(len(WriteQueue) - 1))
            elif c_DrawMode == "FIRST":
                Chunk.append(WriteQueue.pop(0))

        if len(Chunk) > 0:
            icmplib.multiping(
                list(map(lambda v: MakeAddress(*v), Chunk)),
                count=1,
                interval=1,
                timeout=0.01,
                concurrent_tasks=c_ConcurrentPings,
                payload_size=0,
                privileged=c_Privileged
            )
        else:
            time.sleep(0.01)

def main():
    global g_SharedData
    CanvasSize = g_SharedData["CanvasSize"]

    ICMPWorkerThread = threading.Thread(target=ICMPWorkerLogic)
    ICMPWorkerThread.start()

    OriginalTargetImage = Image.open(c_TargetImage)
    TargetImage = OriginalTargetImage.resize((CanvasSize[0], CanvasSize[1]))
    try:
        while g_SharedData["Run"]:
            IterationStart = time.time()
            CanvasResult = requests.get(c_CanvasURL)
            if CanvasResult.status_code != 200:
                print(f"Failed To Acquire Canvas Image. Status Code {CanvasResult.status_code}")
                time.sleep(3)
                continue
            CanvasImage = Image.open(io.BytesIO(CanvasResult.content))

            # Compare Canvas Image With Target Image
            if CanvasImage.size != TargetImage.size:
                print(f"Canvas/Target Size Mismatch, Canvas: {CanvasImage.size} Target: {TargetImage.size}. Resizing...")
                CanvasSize = CanvasImage.size
                TargetImage = OriginalTargetImage.resize((CanvasSize[0], CanvasSize[1]))

            NewQueue = []
            CPXS = CanvasImage.load()
            TPXS = TargetImage.load()
            DoneList = []
            for X in range(CanvasSize[0]):
                for Y in range(CanvasSize[1]):
                    CPX = CPXS[X, Y]
                    TPX = TPXS[X, Y]
                    if not CompareColor(TPX, CPX) and (not [X, Y] in DoneList):
                        DoneList.append([X + 0, Y + 0])
                        CF = (X + 1 < CanvasSize[0]) and (Y + 1 < CanvasSize[1])
                        if CF and (CompareColor(TPX, TPXS[X + 0, Y + 1]) and CompareColor(TPX, TPXS[X + 1, Y + 0]) and CompareColor(TPX, TPXS[X + 1, Y + 1])):
                            NewQueue.append([2, X, Y, TPX[0], TPX[1], TPX[2]])
                            DoneList.append([X + 1, Y + 0])
                            DoneList.append([X + 0, Y + 1])
                            DoneList.append([X + 1, Y + 1])
                        else:
                            NewQueue.append([1, X, Y, TPX[0], TPX[1], TPX[2]])
                if X % 2 == 0:
                    DoneList = []

            if c_DrawMode != "SCATTER":
                NewQueue.sort(key=lambda v: v[0])
            g_SharedData["WriteQueue"] = NewQueue
            print("Iteration Finished(Took {:.2f} Seconds), {} Canvas Operations Are Required         ".format(time.time() - IterationStart, len(g_SharedData["WriteQueue"])), end='\r')
            if len(g_SharedData["WriteQueue"]) == 0:
                time.sleep(2)
    except BaseException as Error:
        print(Error)

    print("Stopping Worker Thread...")
    g_SharedData["Run"] = False
    ICMPWorkerThread.join()




if __name__ == "__main__":
    main()