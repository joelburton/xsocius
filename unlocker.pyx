# Unlocker code; makes a much faster c-based version than the standard Python version.
#
# This needs to be build using ./setup build_ext

cpdef gui_unlock(char width,
                 char height,
                 bytes solution,
                 unsigned short scrambled_cksum):
    cdef unsigned short key
    cdef bytes sq
    cdef bytes sqr
    cdef char*solin = solution
    cdef bytes out

    sq = square(solin, width, height)
    sqr = sq.replace(b'.', b'')

    # people often use keys >7000, so let's sneakily count down
    for key in range(9999, 999, -1):
        out = try_key(width, height, scrambled_cksum, sq, sqr, key)
        if out:
            return (out, key)
    return (False, key)

cdef bytes try_key(char width,
                   char height,
                   unsigned short scrambled_cksum,
                   bytes sq,
                   bytes sqr,
                   unsigned short key):
    cdef unsigned short cksum = 0
    cdef char b
    cdef unsigned short lowbit
    cdef str c
    cdef bytes uncrambled
    cdef bytes sqd
    cdef char*sqdc

    unscrambled = square(
        restore(sq, unscramble_string(sqr, key)),
        height,
        width)
    sqd = square(unscrambled, width, height).replace(b'.', b'')
    sqdc = sqd

    for b in sqdc:
        # right-shift one with wrap-around
        lowbit = (cksum & 0x0001)
        cksum = (cksum >> 1)
        if lowbit: cksum = (cksum | 0x8000)

        # then add in the data and clear any carried bit past 16
        cksum = (cksum + b) & 0xffff
    if cksum == scrambled_cksum:
        return unscrambled

cdef inline bytes nodots(char*datain):
    cdef char[1000] data
    cdef short i
    cdef short j = 0
    for i in range(len(datain)):
        data[j] = datain[i]
        if datain[i] != 46:  # dot
            j += 1
    data[j] = 0
    return data

cdef inline bytes square(bytes data,
                         char w,
                         char h):
    """In [3]: unlocker.square("ABCDEF", 2, 3)
       Out[3]: 'ACEBDF'"""

    cdef char*s = data
    cdef char[1000] out
    cdef unsigned short ptr = 0
    cdef int outer
    cdef int inner

    for outer in range(w):
        for inner in range(h):
            out[ptr] = s[outer + inner * w]
            ptr += 1
    out[ptr] = 0

    return out

cdef inline bytes restore(char*s,
                          char*t):
    cdef char[1000] out
    cdef unsigned short tcount = 0
    cdef unsigned short scount = 0

    for scount in range(len(s)):
        if s[scount] != 46:  # .
            out[scount] = t[tcount]
            tcount += 1
        else:
            out[scount] = b"."
    return out

cdef inline char*unscramble_string(bytes s,
                                   unsigned short key):
    cdef unsigned short l = len(s)
    cdef char k
    cdef unsigned char[4] keys
    cdef char[1000] out
    cdef unsigned short i
    cdef char*s1

    keys[0] = key / 1000
    keys[1] = key % 1000 / 100
    keys[2] = key % 100 / 10
    keys[3] = key % 10

    # loop 0
    s = s[1::2] + s[::2]
    s = s[l - keys[3]:] + s[:l - keys[3]]

    s1 = s
    for i in range(len(s1)):
        out[i] = ((s1[i] - 65 - keys[i % 4]) % 26) + 65
    out[i + 1] = 0
    s = out


    # loop 1
    s = s[1::2] + s[::2]
    s = s[l - keys[2]:] + s[:l - keys[2]]

    s1 = s
    for i in range(len(s1)):
        out[i] = ((s1[i] - 65 - keys[i % 4]) % 26) + 65
    out[i + 1] = 0
    s = out


    # loop 2
    s = s[1::2] + s[::2]
    s = s[l - keys[1]:] + s[:l - keys[1]]

    s1 = s
    for i in range(len(s1)):
        out[i] = ((s1[i] - 65 - keys[i % 4]) % 26) + 65
    out[i + 1] = 0
    s = out


    # loop 3
    s = s[1::2] + s[::2]
    s = s[l - keys[0]:] + s[:l - keys[0]]

    s1 = s
    for i in range(len(s1)):
        out[i] = ((s1[i] - 65 - keys[i % 4]) % 26) + 65
    out[i + 1] = 0
    s = out

    return s
