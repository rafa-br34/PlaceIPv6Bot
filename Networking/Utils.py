
def CalculateChecksum(Data, Checksum=0):
    Len = len(Data)

    i = 0
    while Len > 1:
        Checksum += ((Data[i + 1]) << 8) + (Data[i + 0]) # Add String To Checksum In 16 Bit Pieces
        Checksum &= 0xFFFF_FFFF # Clamp To 32 Bits
        i += 2
        Len -= 2

    if i < len(Data):
        Checksum += (Data[len(Data) - 1])
        Checksum &= 0xFFFF_FFFF # Clamp To 32 Bits

    Checksum = (Checksum >> 16) + (Checksum & 0xFFFF)  # Fold High 16 Bits
    Checksum += (Checksum >> 16)
    return ~Checksum & 0xFFFF