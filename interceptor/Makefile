CC = g++
CFLAGS = -Wall -fPIC -shared
LDFLAGS = -ldl

all: hook.so mlfq_handler

# Compile the LD_PRELOAD interceptor into a shared library (.so)
hook.so: ld_preload.cpp
	$(CC) $(CFLAGS) -o hook.so ld_preload.cpp $(LDFLAGS)

# Compile the MLFQ Dispatcher executable
mlfq_handler: mlfq_handler.cpp
	$(CC) -Wall -o mlfq_handler mlfq_handler.cpp

clean:
	rm -f hook.so mlfq_handler
