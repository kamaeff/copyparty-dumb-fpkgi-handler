#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>
#include <sys/mman.h>
#include "sdk/ps4-libjbc/jailbreak.h"
#include "struct.h"


static const char content_id[0x30] = "{{ PACKAGE_CONTENT_ID }}";
static const char content_url[0x800] = "{{ PACKAGE_CONTENT_URL }}";
static const char content_name[0x259] = "{{ PACKAGE_CONTENT_NAME }}";
static const char icon_url[0x800] = "{{ PACKAGE_ICON_URL }}";
static const char package_type[0x15] = "{{ PACKAGE_TYPE }}";
static const unsigned long size = 0x123456789ABCDEFF;


int(*sceBgftInitialize)(struct bgft_init_params*);
int(*sceBgftDownloadRegisterTask)(struct bgft_download_param*, int*);
int(*sceBgftDebugDownloadRegisterTask)(struct bgft_download_param*, int*);
int(*sceBgftDownloadStartTask)(int);
int(*sceBgftFinalize)(void);
int(*sceBgftServiceIntTerm)(void);

int (*vsnprintf)(char* str, size_t size, const char *format, va_list);
int (*printf)(const char *format, ...);
size_t (*strlcpy)(char* dst, char* src, size_t dst_size);

int (*sceKernelSendNotificationRequest)(int, SceNotificationRequest* req, size_t size, int blocking);

void init_libs() {
	void* bgft = dlopen("/system/common/lib/libSceBgft.sprx", 0);
	sceBgftInitialize = dlsym(bgft, "sceBgftServiceIntInit");
	sceBgftDownloadRegisterTask = dlsym(bgft, "sceBgftServiceDownloadRegisterTask");
	sceBgftDebugDownloadRegisterTask = dlsym(bgft, "sceBgftServiceIntDebugDownloadRegisterPkg");
	sceBgftDownloadStartTask = dlsym(bgft, "sceBgftServiceIntDownloadStartTask");
	sceBgftServiceIntTerm = dlsym(bgft, "sceBgftServiceIntTerm");

	void* libc = dlopen("libSceLibcInternal.sprx", 0);
	vsnprintf = dlsym(libc, "vsnprintf");
	strlcpy = dlsym(libc, "strlcpy");
	printf = dlsym(libc, "printf");

	void* kernel = dlopen("libkernel.sprx", 0);
	if (!kernel) {
		kernel = dlopen("libkernel_web.sprx", 0);
	}
	if (!kernel) {
		kernel = dlopen("libkernel_sys.sprx", 0);
	}
	sceKernelSendNotificationRequest = dlsym(kernel, "sceKernelSendNotificationRequest");
}

// https://github.com/OSM-Made/PS4-Notify
#define notify_bufsize 0x400
#define notify_bufsize_icon 0x800
void printf_notify(char* fmt, ...) {
	SceNotificationRequest req = {};

	va_list args;
	va_start(args, fmt);
	vsnprintf(req.Message, notify_bufsize, fmt, args);
	va_end(args);

	req.Type = 0;
	req.Attribute = 0;
	req.HasIcon = 1;
	req.TargetId = -1;

	strlcpy(req.IconImageUri, icon_url[0] ? icon_url : "cxml://psnotification/tex_default_icon_download", notify_bufsize_icon);
	
	printf("[DEBUG] printf_notify: %s\n", req.Message);
	sceKernelSendNotificationRequest(0, (SceNotificationRequest *)&req, sizeof(SceNotificationRequest), 0);
}

void finalize(struct bgft_init_params* ip) {
	sceBgftServiceIntTerm();
	munmap(ip->mem, ip->size);
}

int main()
{
	init_libs();

	int rv;

	struct bgft_init_params ip = {
		.mem = mmap(NULL, 0x100000, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0),
		.size = 0x100000,
	};
	rv = sceBgftInitialize(&ip);
	if (rv && rv != 0x80990001) {
		printf_notify("PKG DL: BGFT Init Failed %X", rv);
		finalize(&ip);
		return -1;
	}

	struct bgft_download_param bgft_params = {
		.user_id = 0,
		.entitlement_type = 5,
		.id = content_id,
		.content_url = content_url,
		.content_name = content_name,
		.icon_path = icon_url,
		.package_type = package_type,
		.package_sub_type = "",
		.playgo_scenario_id = "0",
		.option = BGFT_TASK_OPTION_DISABLE_CDN_QUERY_PARAM,
		.package_size = size
	};

	int task = BGFT_INVALID_TASK_ID;
	rv = sceBgftDownloadRegisterTask(&bgft_params, &task);
	if (rv != 0x80990088 && task != BGFT_INVALID_TASK_ID) {
		rv = sceBgftDownloadStartTask(task);
		finalize(&ip);
		return 0;
	}

	rv = sceBgftDebugDownloadRegisterTask(&bgft_params, &task);
	if (rv != 0x80990088 && rv != 0x80990086 && task != BGFT_INVALID_TASK_ID) {
		rv = sceBgftDownloadStartTask(task);
		finalize(&ip);
		return 0;
	}
	if (rv == 0x80990088) {
		printf_notify("PKG DL: Package Already Installed!\n%s", content_name);
		finalize(&ip);
		return 0;
	}
	if (rv == 0x80990086){
		printf_notify("PKG DL: Package is already downloading.\n%s", content_name);
		finalize(&ip);
		return 0;
	}
	if (rv == 0x80990039 || rv == 0x80A30026) {
		printf_notify("PKG DL: Insufficient storage space.\nPlease free up space on your hard drive.");
	} else if (rv == 0x80990085) {
		printf_notify("PKG DL: Insufficient storage space.\nPlease free up non fragmented space on your hard drive.");
	} else {
		printf_notify("PKG DL: BGFT Error 0x%X", rv);
	}

	finalize(&ip);
	return -1;
}
