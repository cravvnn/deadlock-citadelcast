// Actual Windows page/OS-copy checks using owned allocations only.
#include "checked_page_read.hpp"
#include "camera_diagnostics.hpp"
#include "test_hero_read_fixture.hpp"
#include <cstdio>
int main(int argc,char**argv){
    assert(argc==2);Fixture fixture;hero::Target target;
    citadelcast_memory::ReadCosts target_cost;
    hero::TargetReader target_reader(fixture.module,citadelcast_memory::CheckedRead(&target_cost));
    assert(target_reader.sample(fixture.camera,target)&&target.handle==Fixture::target_handle&&target.root==hero::Vec({100,200,300}));
    assert(target_cost.passes==2&&target_cost.requests==54&&target_cost.page_queries==54&&target_cost.copies==54&&target_cost.range_queries==0&&target_cost.rejected==0);
    const auto fixture_cost=target_cost;
    const auto original=target;
    Put(fixture.node+hero::kAbsoluteOrigin,std::array<float,3>{111,222,333});
    assert(target_reader.sample(fixture.camera,target)&&target.root==hero::Vec({111,222,333})&&target.same_identity(original));
    Put(fixture.pawn+hero::kEntityIdentity,std::uintptr_t(1));target.handle=0xdead;
    assert(!target_reader.sample(fixture.camera,target)&&target.handle==0xdead);
    citadelcast_memory::ReadCosts camera_cost;void* pointer=nullptr;
    assert(walker_diagnostic::ReadPointer(reinterpret_cast<void*>(fixture.camera),pointer,&camera_cost));
    assert(reinterpret_cast<std::uintptr_t>(pointer)==fixture.module+hero::kCameraTable);
    assert(camera_cost.page_queries==1&&camera_cost.range_queries==0&&camera_cost.copies==1);
    SYSTEM_INFO sys{};GetSystemInfo(&sys);const std::size_t page=sys.dwPageSize;assert(page>=64);
    auto p=reinterpret_cast<std::uintptr_t>(VirtualAlloc(nullptr,page*3,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));assert(p);
    citadelcast_memory::ReadCosts boundary_cost;citadelcast_memory::CheckedRead read(&boundary_cost);
    Put(p,std::uint32_t(42));std::uint32_t value=999;DWORD old{};
    for(DWORD protection:{PAGE_READONLY,PAGE_READWRITE,PAGE_EXECUTE_READ,PAGE_EXECUTE_READWRITE}){
        assert(VirtualProtect(reinterpret_cast<void*>(p),page,protection,&old));
        assert(read(p,&value,4)&&value==42);
    }
    // RPM alone allows execute-only memory on this host. Fresh page protection
    // must still reject it and leave public output unchanged.
    for(DWORD protection:{PAGE_EXECUTE,PAGE_NOACCESS,PAGE_READWRITE|PAGE_GUARD}){
        assert(VirtualProtect(reinterpret_cast<void*>(p),page,protection,&old));value=999;
        assert(!read(p,&value,4)&&value==999);
        MEMORY_BASIC_INFORMATION info{};assert(VirtualQuery(reinterpret_cast<void*>(p),&info,sizeof(info))==sizeof(info));
        assert(info.Protect==protection);
    }
    assert(VirtualProtect(reinterpret_cast<void*>(p),page*3,PAGE_READWRITE,&old));
    // A fresh read sees current bytes and permissions, with no pass/frame cache.
    assert(read(p,&value,4)&&value==42);Put(p,std::uint32_t(43));assert(read(p,&value,4)&&value==43);
    assert(VirtualProtect(reinterpret_cast<void*>(p),page,PAGE_NOACCESS,&old));value=999;
    assert(!read(p,&value,4)&&value==999);read.begin_pass();assert(!read(p,&value,4)&&value==999);
    assert(VirtualProtect(reinterpret_cast<void*>(p),page,PAGE_READWRITE,&old));
    assert(!read(0,&value,4)&&!read(p,nullptr,4)&&!read(p,&value,0)&&!read(p,&value,65)&&!read(UINTPTR_MAX-1,&value,4)&&value==999);
    std::array<unsigned char,12> bytes;bytes.fill(0x77);const auto before=bytes;
    // Crossing inside the same committed/protected allocation is admitted;
    // crossing into another protection region retains the old refusal rule.
    assert(read(p+page-4,bytes.data(),bytes.size()));bytes=before;
    assert(VirtualProtect(reinterpret_cast<void*>(p+page),page,PAGE_READONLY,&old));
    assert(!read(p+page-4,bytes.data(),bytes.size())&&bytes==before);
    assert(VirtualProtect(reinterpret_cast<void*>(p+page),page,PAGE_NOACCESS,&old));
    assert(!read(p+page-4,bytes.data(),bytes.size())&&bytes==before);
    pointer=reinterpret_cast<void*>(0x1234);
    assert(!walker_diagnostic::ReadPointer(reinterpret_cast<void*>(p+page),pointer)&&reinterpret_cast<std::uintptr_t>(pointer)==0x1234);
    assert(VirtualFree(reinterpret_cast<void*>(p+2*page),page,MEM_DECOMMIT));
    assert(!read(p+2*page,&value,4)&&value==999);
    assert(VirtualFree(reinterpret_cast<void*>(p),0,MEM_RELEASE));assert(!read(p,&value,4)&&value==999);
    FILE*out=nullptr;assert(fopen_s(&out,argv[1],"wb")==0);
    std::fputs("{\"target\":",out);fixture_cost.write(out);std::fputs(",\"camera\":",out);camera_cost.write(out);
    std::fputs(",\"boundary\":",out);boundary_cost.write(out);std::fputs("}\n",out);std::fclose(out);
    std::puts("page_checked_read:54 fresh OS field copies/page checks, zero region scans for ordinary target/camera fields; readable/execute-only/guard/protection-change/partial/cross-region/overflow/decommit/free refusal and unchanged-output checks passed");
}
