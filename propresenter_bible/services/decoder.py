class YvesDecoder:
    def decode(self, input_bytes: bytes) -> str:
        i2 = len(input_bytes)
        bArr = bytearray(input_bytes)
        for i3 in range(0, i2, 2):
            i4 = i3 + 1
            if i2 > i4:
                temp_i4 = ((bArr[i3] & 255) >> 5) | ((bArr[i3] & 255) << 3)
                bArr[i3] = ((bArr[i4] & 255) >> 5) | ((bArr[i4] & 255) << 3) & 0xFF
                bArr[i4] = temp_i4 & 0xFF
            else:
                bArr[i3] = (((bArr[i3] & 255) >> 5) | ((bArr[i3] & 255) << 3)) & 0xFF
        return bytes(bArr).decode("UTF-8", errors="ignore")

    def read_file(self, path: str) -> str:
        with open(path, 'rb') as handle:
            return self.decode(handle.read())


def decode_yves_bytes(input_bytes: bytes) -> str:
    return YvesDecoder().decode(input_bytes)

