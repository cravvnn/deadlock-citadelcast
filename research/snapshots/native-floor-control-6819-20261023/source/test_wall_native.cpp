#include "gametrace.h"
#include "wall_native.hpp"
#include "wall_schedule.hpp"
#include <cstdio>
#include <new>
#include <stdexcept>
#include <limits>
using namespace wall_query;
void check(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
template<class T>T field(const void* b,std::size_t at){T v{};std::memcpy(&v,static_cast<const std::byte*>(b)+at,sizeof(T));return v;}
int main(){try{
    unsigned count=0;auto test=[&](const char* name,auto f){f();++count;std::printf("PASS %s\n",name);};
    static_assert(sizeof(Ray_t)==0x30&&sizeof(CTraceFilter)==0x48&&sizeof(CGameTrace)==0xc0);
    static_assert(offsetof(CTraceFilter,m_bIterateEntities)==0x40&&offsetof(CGameTrace,m_flFraction)==0xac);
    const Request q{{1,2,3},{101,2,3},collision_contract::Kind::Sphere,8};
    test("sphere/line descriptors agree with SDK initialization",[&]{
        for(float radius:{0.f,8.f}){auto r=q;r.radius=radius;r.kind=radius?collision_contract::Kind::Sphere:collision_contract::Kind::Line;
            const auto actual=MakeShape(r);Ray_t sdk(Vector(0,0,0),radius);
            check(std::memcmp(actual.bytes.data(),&sdk,16)==0,"shape center/radius");
            check(field<std::uint8_t>(actual.bytes.data(),0x28)==static_cast<std::uint8_t>(sdk.m_eType),"shape type");}
    });
    test("static native-camera filter matches SDK data fields",[]{
        alignas(CTraceFilter) std::array<std::byte,sizeof(CTraceFilter)> storage{};
        auto* sdk=::new(storage.data()) CTraceFilter(0x20000000001081ull,3,false);
        sdk->m_nInteractsExclude=0x14000000202c0000ull;
        sdk->m_nObjectSetMask=RNQUERY_OBJECTS_STATIC;
        const auto actual=MakeFilter(0x12345678);
        check(field<std::uintptr_t>(actual.bytes.data(),0)==0x12345678,"filter vtable");
        check(std::memcmp(actual.bytes.data()+8,storage.data()+8,0x39)==0,"filter complete data fields");
        check(field<std::uint8_t>(actual.bytes.data(),0x39)==0x49,"native filter flags");
        check(field<std::uint8_t>(actual.bytes.data(),0x40)==0,"iteration disabled");
        check(field<std::uint8_t>(actual.bytes.data(),0x37)==1,"static object set");
        sdk->~CTraceFilter();
    });
    test("six native arguments and aligned output are preserved",[&]{
        int calls=0;auto result=Invoke([&](void* holder,const void* shape,const float* start,const float* end,void* filter,void* output){
            ++calls;check(holder==reinterpret_cast<void*>(0x1234),"query holder");
            check(field<float>(shape,0xc)==8&&field<std::uint8_t>(shape,0x28)==1,"shape argument");
            check(std::memcmp(start,q.start.data(),12)==0&&std::memcmp(end,q.end.data(),12)==0,"segment arguments");
            check(field<std::uintptr_t>(filter,0)==0x3456,"filter argument");
            check(reinterpret_cast<std::uintptr_t>(output)%16==0,"output alignment");
            auto* out=static_cast<std::byte*>(output);std::memcpy(out+0x78,start,12);std::memcpy(out+0x84,end,12);
            const float fraction=.5f;std::memcpy(out+0xac,&fraction,4);out[0xba]=std::byte(1);return true;
        },reinterpret_cast<void*>(0x1234),0x3456,q);
        check(calls==1&&result.called&&result.guard_ok&&result.result.hit,"single bounded invocation");
        check(field<float>(result.result.bytes.data(),0xac)==.5f,"numeric output copied");
    });
    test("null context or malformed request never invokes",[&]{
        int calls=0;auto fake=[&](auto...){++calls;return false;};
        check(!Invoke(fake,nullptr,1,q).called,"null holder");check(!Invoke(fake,reinterpret_cast<void*>(1),0,q).called,"null filter");
        auto bad=q;bad.radius=-1;check(!Invoke(fake,reinterpret_cast<void*>(1),1,bad).called,"invalid radius");check(calls==0,"no calls");
    });
    test("result redzone change prevents copied output",[&]{
        auto result=Invoke([](void*,const void*,const float*,const float*,void*,void* output){
            auto* scratch=reinterpret_cast<Scratch*>(static_cast<std::byte*>(output)-offsetof(Scratch,bytes));
            scratch->suffix[0]=0;return false;
        },reinterpret_cast<void*>(1),1,q);
        check(result.called&&!result.guard_ok,"guard fault");
        check(result.result.bytes==std::array<std::byte,0xc0>{},"no corrupted result publication");
    });
    test("native input mutation refuses output",[&]{
        auto result=Invoke([](void*,const void*,const float*,const float*,void* filter,void*){
            static_cast<std::byte*>(filter)[0x37]=std::byte(0xf);return false;
        },reinterpret_cast<void*>(1),1,q);
        check(result.called&&!result.guard_ok,"unexpected filter mutation");
    });
    test("segment extends native eye by64 and shares both paths",[]{
        std::array<Request,2> out;check(Requests({0,0,0},{100,0,48},out),"valid camera bearing");
        check(out[0].start==Vec3({0,0,48})&&out[0].end==Vec3({164,0,48}),"known segment");
        check(out[0].start==out[1].start&&out[0].end==out[1].end&&out[1].radius==8,"same comparison segment");
        check(!Requests({0,0,0},{0,0,48},out),"degenerate bearing");
        check(!Requests({0,0,0},{1000,0,48},out),"unbounded bearing");
    });
    test("manual samples require saving and stop at three",[]{
        Schedule s;for(unsigned i=0;i<3;++i){check(s.arm(10+i*10,true),"arm");check(!s.due(12+i*10,true),"countdown");check(s.due(13+i*10,true),"due");s.finish(true,"complete");check(!s.arm(15+i*10,true),"save gate");s.saved();}
        check(!s.arm(50,true)&&s.count()==3,"hard sample limit");
    });
    test("lost gate or invalid clock blocks further attempts",[]{
        for(unsigned i=0;i<3;++i){Schedule s;s.arm(1,true);
            if(i==0)s.due(2,false);if(i==1)s.due(0,true);if(i==2)s.due(5.1,true);
            check(s.blocked()&&!s.active(),"failure latched");s.saved();check(!s.arm(10,true),"no retry");}
    });
    test("native-call budget failure denies the next query",[]{
        Budget fast(0);check(fast.finish_call(0,.001)&&fast.allowed(.002),"normal query budget");
        Budget slow(0);check(!slow.finish_call(0,.003)&&!slow.allowed(.004),"slow query blocks following call");
        Budget expired(0);check(!expired.allowed(.011),"whole-sample deadline");
        Budget backwards(1);check(!backwards.finish_call(1,.9)&&!backwards.allowed(1.1),"invalid native clock blocks");
        Budget invalid(std::numeric_limits<double>::quiet_NaN());check(!invalid.allowed(1),"invalid start time");
    });
    std::printf("%u native wall boundary scenarios passed; injected fakes only\n",count);
}catch(const std::exception& e){std::fprintf(stderr,"FAIL %s\n",e.what());return 1;}}
