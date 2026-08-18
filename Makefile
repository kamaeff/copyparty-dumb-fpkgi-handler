REMOTE_HOST := builder@build-server
REMOTE_DIR := builds/copyparty-fpkg-toolbox

s_payload := src/payload
s_sdk := $(s_payload)/sdk
s_lib := $(s_sdk)/lib
s_py := src/fpkg_toolbox.py
s_css := src/web/style.css
s_js := src/web/script.js

t_lib := build/lib.a
t_elf := build/payload.elf
t_bin := build/payload.bin
t_py := build/fpkg_toolbox.py

all: $(t_py)

clean:
	rm -f build/* 
	rm -f $(s_sdk)/lib.a $(s_sdk)/*.o

remote:
	rsync -az --delete --mkpath \
		--exclude build/ \
		--exclude .git/ \
		./ $(REMOTE_HOST):$(REMOTE_DIR)/
	ssh $(REMOTE_HOST) 'cd $(REMOTE_DIR) && make'
	rsync -az --delete $(REMOTE_HOST):$(REMOTE_DIR)/build/ ./build/

remote-clean:
	ssh $(REMOTE_HOST) 'rm -rf $(REMOTE_DIR)'

$(t_lib):
	cd $(s_lib) && make
	mkdir -p build && mv $(s_lib)/lib.a $(t_lib)

$(t_elf): $(t_lib) $(s_payload)/main.c
	gcc -g -mcmodel=small -isystem $(s_sdk)/freebsd-headers -nostdinc -nostdlib -fno-stack-protector -static $(t_lib) $(s_payload)/main.c $(s_sdk)/ps4-libjbc/*.c -Wl,-gc-sections -o build/payload.elf -fPIE -ffreestanding

$(t_bin): $(t_elf)
	objcopy $(t_elf) --only-section .text --only-section .data --only-section .bss --only-section .rodata -O binary $(t_bin)
	file $(t_bin) | fgrep -q 'payload.bin: DOS executable (COM)'

$(t_py): $(t_bin) $(s_py) $(s_css) $(s_js) scripts/make_py.py
	python3 scripts/make_py.py