#include "floor_control.hpp"
#include "wall_native.hpp"
#include <cstdio>
#include <limits>
#include <stdexcept>
using namespace collision_contract;
void check(bool v,const char* why){if(!v)throw std::runtime_error(why);}
// Analytic fixture independent of the request generator: solid half-space z<=100.
// It is a fake query, not Deadlock geometry or a native call.
struct Fixture {
    std::array<Request,2> requests{};
    std::array<Reading,2> readings{};
    unsigned calls=0;bool valid=false,guards=true;
    explicit Fixture(float plane){
        check(floor_control::Requests({12,34,100},requests),"floor request rejected");
        const Context c{1,2,3,4,5,true,true,true,true,true,true,true,true};
        OneSample batch;batch.arm();
        valid=batch.run(requests,readings,[&]{return c;},[&](const Request& q){
            auto invocation=wall_query::Invoke([&](void*,const void* shape,const float* a,const float* b,void*,void* output){
                ++calls;
                const auto* data=static_cast<const std::byte*>(shape);
                const float radius=Read<float>({data,0x30},0xc);
                const float surface=plane+radius;
                const bool inside=a[2]<=surface;
                const bool hit=inside||b[2]<surface;
                const float fraction=inside?0.f:hit?(a[2]-surface)/(a[2]-b[2]):1.f;
                Vec3 start{a[0],a[1],a[2]},end{};
                for(unsigned i=0;i<3;++i)end[i]=a[i]+fraction*(b[i]-a[i]);
                auto* raw=static_cast<std::byte*>(output);
                auto put=[&](std::size_t at,const auto& v){std::memcpy(raw+at,&v,sizeof(v));};
                put(0x78,start);put(0x84,end);put(0xac,fraction);
                const auto tag=hit?Read<std::uint8_t>({data,0x30},0x28):std::uint8_t(0);
                put(0xba,tag);put(0xbb,std::uint8_t(inside));return hit;
            },reinterpret_cast<void*>(1),2,q);
            guards=guards&&invocation.called&&invocation.guard_ok;
            return invocation.result;
        });
    }
};
int main(){try{
    unsigned count=0;auto test=[&](const char* name,auto f){f();++count;std::printf("PASS %s\n",name);};
    test("vertical comparison segment brackets grounded root",[]{
        std::array<Request,2> q;check(floor_control::Requests({12,34,100},q),"valid floor segment");
        check(q[0].start==Vec3({12,34,164})&&q[0].end==Vec3({12,34,-28}),"192-unit downward segment");
        check(q[0].start==q[1].start&&q[0].end==q[1].end&&q[0].kind==Kind::Line&&q[0].radius==0&&q[1].kind==Kind::Sphere&&q[1].radius==8,"same segment, unchanged primitives");
    });
    test("analytic plane yields two validated outside-start contacts",[]{
        Fixture f(100);check(f.valid&&f.guards&&f.calls==2,"two valid guarded fake queries");
        check(floor_control::ContactPair(f.readings),"positive floor control");
        check(std::abs(f.readings[0].fraction-1.f/3)<1e-6&&std::abs(f.readings[1].fraction-7.f/24)<1e-6,"independent analytic fractions");
        check(f.readings[0].end[2]==100&&f.readings[1].end[2]==108,"line plane and sphere-center clearance");
    });
    test("both misses remain valid data but fail expected contact",[]{
        Fixture f(-500);check(f.valid&&f.guards&&f.calls==2,"valid no-contact records");
        check(!floor_control::ContactPair(f.readings),"no false positive contact");
    });
    test("start-solid results cannot qualify a usable floor control",[]{
        Fixture f(300);check(f.valid&&f.calls==2,"decoded solid-start results");
        check(!floor_control::ContactPair(f.readings),"solid-start control refused");
    });
    test("one-sided contact and endpoint equality do not qualify",[]{
        Fixture f(100);f.readings[0].outcome=Outcome::NoContact;
        check(!floor_control::ContactPair(f.readings),"one-sided contact refused");
        Fixture g(100);g.readings[0].fraction=1;check(!floor_control::ContactPair(g.readings),"endpoint not usable control");
    });
    test("nonfinite and coordinate-limit roots never produce requests",[]{
        std::array<Request,2> out;
        check(!floor_control::Requests({0,0,std::numeric_limits<float>::quiet_NaN()},out),"nan root");
        check(!floor_control::Requests({1000001,0,0},out),"coordinate bound");
        check(!floor_control::Requests({0,0,999990},out),"upper endpoint bound");
        check(!floor_control::Requests({0,0,-999990},out),"lower endpoint bound");
    });
    std::printf("%u floor-control scenarios passed; analytic fixtures only, no engine\n",count);
}catch(const std::exception& e){std::fprintf(stderr,"FAIL %s\n",e.what());return 1;}}
