# Open Watcom wmake, from DOS16. -0 emits 8086/8088 instructions (V20 compatible).
CC = wcl
CFLAGS = -q -bt=dos -ms -0 -os -s -wx -w4

all: RA16.EXE

RA16.EXE: ra16.c sim.c sim.h testsim.c
	$(CC) $(CFLAGS) -fe=RA16.EXE -fm=RA16.MAP ra16.c sim.c testsim.c

clean: .SYMBOLIC
	rm -f *.obj *.o RA16.EXE RA16.MAP FRAME.RAW PASS.TXT
