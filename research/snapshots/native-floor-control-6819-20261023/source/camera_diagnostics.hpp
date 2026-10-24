#pragma once
#include <windows.h>
#include <cstdint>
#include <cstring>
#include "camera_diagnostic_types.hpp"
#include "checked_page_read.hpp"
namespace walker_diagnostic {
struct Snapshot {
    bool manager_present=false,manager_readable=false,manager_reviewed=false;
    bool slot0_same=false,active_present=false,retained_present=false,active_default=false,transition_present=false;
    std::uintptr_t manager_table=0,active_table=0,retained_table=0;
    const char* manager_type="not read";const char* active_type="not read";const char* retained_type="not read";
};
// Read only within this process. Unknown manager layouts are never traversed.
// This does not install hooks, select a camera, alter settings or accept a gate.
bool ReadPointer(const void* address,void*& value,citadelcast_memory::ReadCosts* cost=nullptr) {
    citadelcast_memory::CheckedRead read(cost);
    return read(reinterpret_cast<std::uintptr_t>(address),&value,sizeof(value));
}
const char* DiagnosticType(void* object,std::uintptr_t client,std::uintptr_t& table) {
    if(!object) return "none";
    void* vtable{};if(!ReadPointer(object,vtable)) return "unreadable object";
    const auto absolute=reinterpret_cast<std::uintptr_t>(vtable);
    if(absolute<client || absolute-client>=kDiagnosticClientImageSize) return "table outside reviewed client";
    table=absolute-client;
    for(const auto& known:kDiagnosticCameraTypes) if(known.table==table) return known.name;
    return "unlisted client table";
}
Snapshot ObserveCamera(void* current,void* slot0,std::uintptr_t client,std::uintptr_t manager_table) {
    Snapshot result;
    result.manager_present=current!=nullptr;result.slot0_same=current && current==slot0;
    result.manager_type=DiagnosticType(current,client,result.manager_table);
    void* table{};result.manager_readable=current && ReadPointer(current,table);
    result.manager_reviewed=result.manager_readable && reinterpret_cast<std::uintptr_t>(table)==client+manager_table;
    if(!result.manager_reviewed) return result;
    void* active{};void* retained{};void* transition{};
    if(!ReadPointer(static_cast<unsigned char*>(current)+0x28,active) ||
       !ReadPointer(static_cast<unsigned char*>(current)+0x20,retained) ||
       !ReadPointer(static_cast<unsigned char*>(current)+0x30,transition)) return result;
    result.active_present=active!=nullptr;result.retained_present=retained!=nullptr;
    result.active_default=active && active==retained;result.transition_present=transition!=nullptr;
    result.active_type=DiagnosticType(active,client,result.active_table);
    result.retained_type=DiagnosticType(retained,client,result.retained_table);
    return result;
}
}
