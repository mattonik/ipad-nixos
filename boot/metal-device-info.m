// Offline iOS 15 compatibility probe: report the default Metal device by public API.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

int main(void) {
    @autoreleasepool {
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        if (!device) {
            fputs("Metal device unavailable\n", stderr);
            return 1;
        }
        printf("%s\n", device.name.UTF8String);
    }
    return 0;
}
