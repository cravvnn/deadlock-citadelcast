#include "camera_diagnostics.hpp"
#include <array>
#include <cassert>
#include <cstdio>
#include <cstring>

int main() {
    using namespace walker_diagnostic;
    constexpr std::uintptr_t base=0x100000000ULL;
    constexpr std::uintptr_t manager_table=0x277d030;
    constexpr std::uintptr_t free_table=0x10;
    std::uintptr_t camera_type_table=0;
    for(const auto& t:kDiagnosticCameraTypes)
        if(std::strcmp(t.name,"CFreeCamera")==0) camera_type_table=t.table;
    assert(camera_type_table);
    std::array<std::uintptr_t,8> manager{};
    std::array<std::uintptr_t,2> camera{base+camera_type_table,0};
    manager[0]=base+manager_table;
    manager[0x28/8]=reinterpret_cast<std::uintptr_t>(camera.data());
    auto original_manager=manager;auto original_camera=camera;
    auto roaming=ObserveCamera(manager.data(),manager.data(),base,manager_table);
    assert(roaming.manager_reviewed && roaming.active_present && !roaming.retained_present);
    assert(!roaming.active_default && roaming.slot0_same);
    assert(std::strcmp(roaming.active_type,"CFreeCamera")==0);
    assert(manager==original_manager && camera==original_camera);
    auto absent=ObserveCamera(nullptr,manager.data(),base,manager_table);
    assert(!absent.manager_present && !absent.manager_reviewed && !absent.active_present);
    manager[0]=base+free_table;
    // Never traverse an unknown manager layout, even when its field resembles a camera.
    auto unknown=ObserveCamera(manager.data(),manager.data(),base,manager_table);
    assert(!unknown.manager_reviewed && !unknown.active_present);
    manager[0]=base+manager_table;
    manager[0x20/8]=manager[0x28/8];
    auto retained=ObserveCamera(manager.data(),manager.data(),base,manager_table);
    assert(retained.active_default && retained.retained_present);
    manager[0x20/8]=0;manager[0x28/8]=0;
    auto both_absent=ObserveCamera(manager.data(),manager.data(),base,manager_table);
    assert(!both_absent.active_default);
    void* pointer{};
    assert(!ReadPointer(nullptr,pointer));
    SYSTEM_INFO info{};GetSystemInfo(&info);
    auto pages=static_cast<unsigned char*>(VirtualAlloc(nullptr,info.dwPageSize*2,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE));
    assert(pages);
    DWORD old{};
    assert(VirtualProtect(pages+info.dwPageSize,info.dwPageSize,PAGE_NOACCESS,&old));
    assert(!ReadPointer(pages+info.dwPageSize-sizeof(void*)/2,pointer));
    assert(!ReadPointer(pages+info.dwPageSize,pointer));
    assert(VirtualProtect(pages,info.dwPageSize,PAGE_READWRITE|PAGE_GUARD,&old));
    assert(!ReadPointer(pages,pointer));
    assert(VirtualFree(pages,0,MEM_RELEASE));
    std::puts("camera_diagnostics: null/unknown layout, owned-memory immutability, named type, null active/default, unreadable/guard/cross-page checks passed");
}
