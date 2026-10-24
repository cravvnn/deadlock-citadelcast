#include "owned_slot.hpp"
#include <cassert>

static int Old() { return 17; }
static int Hook() { return 29; }
static int Other() { return 31; }
int main() {
    auto table=reinterpret_cast<void**>(VirtualAlloc(nullptr,4096,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
    assert(table); table[0]=reinterpret_cast<void*>(&Old);
    DWORD old{};assert(VirtualProtect(table,4096,PAGE_READONLY,&old));
    OwnedSlot hook;
    assert(!hook.install(nullptr,reinterpret_cast<void*>(&Old),reinterpret_cast<void*>(&Hook)));
    assert(!hook.install(reinterpret_cast<void**>(1),reinterpret_cast<void*>(&Old),reinterpret_cast<void*>(&Hook)));
    assert(!hook.install(table,reinterpret_cast<void*>(&Other),reinterpret_cast<void*>(&Hook)));
    assert(reinterpret_cast<int(*)()>(table[0])()==17);
    assert(hook.install(table,reinterpret_cast<void*>(&Old),reinterpret_cast<void*>(&Hook)));
    assert(reinterpret_cast<int(*)()>(table[0])()==29);
    MEMORY_BASIC_INFORMATION info{};assert(VirtualQuery(table,&info,sizeof(info)));
    assert(info.Protect==PAGE_READONLY);
    assert(hook.install(table,reinterpret_cast<void*>(&Old),reinterpret_cast<void*>(&Hook)));
    assert(hook.restore());assert(reinterpret_cast<int(*)()>(table[0])()==17);
    assert(hook.restore());
    assert(hook.install(table,reinterpret_cast<void*>(&Old),reinterpret_cast<void*>(&Hook)));
    assert(VirtualProtect(table,4096,PAGE_READWRITE,&old));
    table[0]=reinterpret_cast<void*>(&Other);
    assert(VirtualProtect(table,4096,PAGE_READONLY,&old));
    assert(!hook.restore());assert(reinterpret_cast<int(*)()>(table[0])()==31);
    VirtualFree(table,0,MEM_RELEASE);
}
