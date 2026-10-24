#include "lifecycle.hpp"
#include "hooks.hpp"
#include <cassert>
#include <vector>

static void* original_connect{};
static void* original_disconnect{};
static int ForwardConnect() { return 17; }
static int ForwardDisconnect() { return 29; }
static int HookConnect() { assert(original_connect); return reinterpret_cast<int(*)()>(original_connect)(); }
static int HookDisconnect() { assert(original_disconnect); return reinterpret_cast<int(*)()>(original_disconnect)(); }

int main() {
    OwnedRegistration registration;
    std::vector<int> order;
    assert(!registration.connect(false, [&] { order.push_back(1); }));
    assert(order.empty());
    registration.disconnect([&] { order.push_back(2); }, [&] { order.push_back(3); });
    assert((order == std::vector<int>{3}));
    order.clear();
    assert(registration.connect(true, [&] { order.push_back(1); }));
    assert(registration.connect(true, [&] { order.push_back(9); }));
    registration.disconnect([&] { order.push_back(2); }, [&] { order.push_back(3); });
    registration.disconnect([&] { order.push_back(9); }, [&] { order.push_back(3); });
    assert((order == std::vector<int>{1,2,3,3}));
    assert(registration.connect(true, [&] { order.push_back(4); }));
    registration.disconnect([&] { order.push_back(5); }, [&] { order.push_back(6); });
    assert((order == std::vector<int>{1,2,3,3,4,5,6}));

    auto table = reinterpret_cast<void**>(VirtualAlloc(nullptr, 4096, MEM_COMMIT|MEM_RESERVE, PAGE_READWRITE));
    assert(table);
    table[0] = reinterpret_cast<void*>(&ForwardConnect);
    table[1] = reinterpret_cast<void*>(&ForwardDisconnect);
    DWORD old{}; assert(VirtualProtect(table,4096,PAGE_READONLY,&old));
    assert(InstallOwnedPair(table, reinterpret_cast<void*>(&HookConnect), reinterpret_cast<void*>(&HookDisconnect),
                            &original_connect, &original_disconnect));
    assert(reinterpret_cast<int(*)()>(table[0])() == 17);
    assert(reinterpret_cast<int(*)()>(table[1])() == 29);
    MEMORY_BASIC_INFORMATION info{}; assert(VirtualQuery(table,&info,sizeof(info)));
    assert(info.Protect == PAGE_READONLY);
    VirtualFree(table,0,MEM_RELEASE);
    return 0;
}
