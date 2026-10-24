// Real Windows APIs on private allocations only. No game, process discovery,
// desktop input, external handles, offsets inferred from runtime or attachment.
#include "hero_checked_read.hpp"
#include "hero_target.hpp"
#include <cassert>
#include <cstdio>
#include <limits>
#include "test_hero_read_fixture.hpp"
int main(int argc,char**argv){
    assert(argc==2);Fixture f;hero::Target target;hero::ReadCosts costs;
    hero::TargetReader reader(f.module,hero::CheckedRead(&costs));
    assert(reader.sample(f.camera,target)&&target.handle==Fixture::target_handle&&target.root==hero::Vec({100,200,300}));
    // The old reader makes54 region queries for this exact successful double
    // sample. Validate the real new boundary, not an artificial wall-time goal.
    assert(costs.passes==2&&costs.requests==54&&costs.copies==54&&costs.rejected==0);
    assert(costs.queries<=12&&costs.region_hits>=42&&costs.queries+costs.region_hits==54);
    const auto initial_costs=costs;
    const auto baseline=target;
    // Reused metadata never reuses field data. Both serial and origin changes
    // are still read and rejected/updated by the original target owner.
    Put(f.node+hero::kAbsoluteOrigin,std::array<float,3>{111,222,333});
    assert(reader.sample(f.camera,target)&&target.root==hero::Vec({111,222,333})&&target.same_identity(baseline));
    Put(f.pawn+hero::kEntityIdentity,std::uintptr_t(1));target.handle=0xdead;
    assert(!reader.sample(f.camera,target)&&target.handle==0xdead);
    Put(f.pawn+hero::kEntityIdentity,f.chunk+0x70*(Fixture::target_handle&0x1ff));
    struct MutateBetweenPasses {
        hero::CheckedRead checked;std::uintptr_t node;unsigned pass=0;
        void begin_pass(){
            if(++pass==2)Put(node+hero::kAbsoluteOrigin,std::array<float,3>{112,222,333});
            checked.begin_pass();
        }
        bool operator()(std::uintptr_t at,void* out,std::size_t size){return checked(at,out,size);}
    };
    // A changing target's second fresh sample must still fail coherence.
    hero::TargetReader changing(f.module,MutateBetweenPasses{hero::CheckedRead{},f.node});
    assert(!changing.sample(f.camera,target)&&target.handle==0xdead);
    // Bounds, permissions, protection changes and deallocation below operate
    // on separate private pages, never the target fixture or a game object.
    auto p=reinterpret_cast<std::uintptr_t>(VirtualAlloc(nullptr,0x20000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));assert(p);
    hero::CheckedRead read;read.begin_pass();std::uint32_t value=0;
    Put(p,std::uint32_t(42));assert(read(p,&value,4)&&value==42);
    Put(p,std::uint32_t(43));assert(read(p,&value,4)&&value==43);
    DWORD old{};value=999;
    // Same-pass permission changes are checked by every OS read, without a
    // raw dereference. Guard pages remain guarded after a refused read.
    for(DWORD protection:{PAGE_NOACCESS,PAGE_READWRITE|PAGE_GUARD}){
        assert(VirtualProtect(reinterpret_cast<void*>(p),4096,protection,&old));
        assert(!read(p,&value,4)&&value==999);
        MEMORY_BASIC_INFORMATION after{};assert(VirtualQuery(reinterpret_cast<void*>(p),&after,sizeof(after))==sizeof(after));
        assert(after.Protect==protection);
        read.begin_pass();assert(!read(p,&value,4)&&value==999);
        assert(VirtualProtect(reinterpret_cast<void*>(p),4096,PAGE_READWRITE,&old));
        read.begin_pass();assert(read(p,&value,4)&&value==43);value=999;
    }
    assert(VirtualProtect(reinterpret_cast<void*>(p),4096,PAGE_EXECUTE,&old));
    read.begin_pass();assert(!read(p,&value,4)&&value==999);
    assert(VirtualProtect(reinterpret_cast<void*>(p),4096,PAGE_READWRITE,&old));
    read.begin_pass();assert(!read(0,&value,4)&&!read(p,nullptr,4)&&!read(p,&value,0));
    assert(!read(p,&value,65)&&!read(UINTPTR_MAX-1,&value,4)&&value==999);
    assert(VirtualProtect(reinterpret_cast<void*>(p+4096),4096,PAGE_NOACCESS,&old));
    std::array<unsigned char,12> bytes;bytes.fill(0x77);const auto before=bytes;
    read.begin_pass();assert(!read(p+4092,bytes.data(),bytes.size())&&bytes==before);
    assert(VirtualProtect(reinterpret_cast<void*>(p+4096),4096,PAGE_READWRITE,&old));
    // More than16 regions takes a fresh-query fallback; it cannot accept an
    // unchecked range or reuse permission/data from an evicted region.
    for(unsigned n=0;n<32;++n)assert(VirtualProtect(reinterpret_cast<void*>(p+4096*n),4096,n%2?PAGE_READONLY:PAGE_READWRITE,&old));
    read.begin_pass();for(unsigned n=0;n<32;++n)assert(read(p+4096*n,&value,4));
    assert(VirtualFree(reinterpret_cast<void*>(p),0,MEM_RELEASE));value=999;
    assert(!read(p,&value,4)&&value==999);read.begin_pass();assert(!read(p,&value,4)&&value==999);
    FILE*out=nullptr;assert(fopen_s(&out,argv[1],"wb")==0);initial_costs.write(out);std::fputs("\n",out);std::fclose(out);
    std::printf("hero_checked_read:54 fresh field reads/two coherent passes; %llu region queries instead of54; no data cache; permissions/guard/partial/bounds/deallocation/pass-refresh/serial/pose-change refusals passed\n",static_cast<unsigned long long>(initial_costs.queries));
}
