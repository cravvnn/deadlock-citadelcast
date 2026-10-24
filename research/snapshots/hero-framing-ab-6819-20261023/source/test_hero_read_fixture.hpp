#pragma once
#include "hero_target.hpp"
#include <windows.h>
#include <cassert>
#include <cstring>
template<class T>void Put(std::uintptr_t at,const T& value){std::memcpy(reinterpret_cast<void*>(at),&value,sizeof(value));}
struct Fixture {
    std::uintptr_t module,block,controller,observer,services,pawn,node,camera,system,chunk;
    static constexpr std::uint32_t observer_handle=0x1201,target_handle=0x1402;
    Fixture(){
        module=reinterpret_cast<std::uintptr_t>(VirtualAlloc(nullptr,hero::kClientImageSize,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));
        block=reinterpret_cast<std::uintptr_t>(VirtualAlloc(nullptr,0x20000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));assert(module&&block);
        controller=block;observer=block+0x1000;services=block+0x2000;pawn=block+0x3000;
        node=block+0x4000;camera=block+0x5000;system=block+0x6000;chunk=block+0x10000;
        Put(module+hero::kEntityList,system);Put(module+hero::kController,controller);
        Put(controller,module+hero::kControllerTable);Put(controller+0x6bc,observer_handle);
        for(auto entry:{std::pair{observer_handle,observer},std::pair{target_handle,pawn}}){
            Put(system+8*((entry.first&0x7fff)>>9),chunk);
            const auto identity=chunk+0x70*(entry.first&0x1ff);
            Put(identity,entry.second);Put(identity+0x10,entry.first);Put(entry.second+hero::kEntityIdentity,identity);
        }
        Put(camera,module+hero::kCameraTable);Put(camera+0xb0,target_handle);
        Put(observer,module+hero::kObserverPawnTable);Put(observer+hero::kObserverServices,services);
        Put(services,module+hero::kServicesTable);Put(module+hero::kServicesTable+0xf0,module+hero::kGetMode);
        Put(module+hero::kServicesTable+0x100,module+hero::kGetTarget);
        Put(services+0x48,static_cast<unsigned char>(3));Put(services+0x4c,target_handle);
        Put(pawn,module+hero::kPlayerPawnTable);Put(pawn+hero::kSceneNode,node);
        Put(node,module+hero::kWrappedSkeletonTable);Put(node+hero::kNodeOwner,pawn);
        Put(node+hero::kAbsoluteOrigin,std::array<float,3>{100,200,300});
    }
    ~Fixture(){assert(VirtualFree(reinterpret_cast<void*>(module),0,MEM_RELEASE));assert(VirtualFree(reinterpret_cast<void*>(block),0,MEM_RELEASE));}
};
