#include "query_contract.hpp"
#include <cstdio>
#include <limits>
#include <stdexcept>
using namespace collision_contract;
void require(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
template<class T>void put(RawResult& r,std::size_t at,T value){std::memcpy(r.bytes.data()+at,&value,sizeof(T));}
Context Ready(){return {11,22,33,44,55,true,true,true,true,true,true,true,true};}
Request Line(){return {{10,20,30},{100,20,30},Kind::Line,0};}
RawResult Fixture(Request q,float fraction=1,bool solid=false) {
    RawResult r;put(r,0x78,q.start);put(r,0x84,q.end);put(r,0xac,fraction);
    put(r,0xba,static_cast<std::uint8_t>(q.kind));put(r,0xbb,std::uint8_t(solid));
    r.hit=fraction<1||solid;return r;
}
int main(){
  try {
    unsigned cases=0;
    auto test=[&](const char* name,auto body){body();++cases;std::printf("PASS %s\n",name);};
    const auto q=Line();const auto context=Ready();
    test("finite no-contact is query-specific",[&]{auto r=Fixture(q);require(Decode(r.bytes,q,r.hit,context,context).outcome==Outcome::NoContact,"clear");});
    test("fraction contact",[&]{auto r=Fixture(q,.25f);require(Decode(r.bytes,q,r.hit,context,context).outcome==Outcome::Contact,"contact");});
    test("start-solid at fraction one remains contact",[&]{auto r=Fixture(q,1,true);require(Decode(r.bytes,q,r.hit,context,context).outcome==Outcome::Contact,"inside");});
    test("native null-world false is not clearance",[&]{auto r=Fixture(q);auto c=context;c.world=0;require(Decode(r.bytes,q,false,c,c).outcome==Outcome::Invalid,"missing world");});
    test("wrong extent refused",[&]{auto r=Fixture(q);require(Decode(std::span(r.bytes).first(0xbf),q,false,context,context).outcome==Outcome::Invalid,"extent");});
    test("NaN and out-of-range fractions refused",[&]{for(float f:{std::numeric_limits<float>::quiet_NaN(),-0.01f,1.01f}){auto r=Fixture(q,f);require(Decode(r.bytes,q,r.hit,context,context).outcome==Outcome::Invalid,"fraction");}});
    test("nonfinite endpoint refused",[&]{auto r=Fixture(q);put(r,0x84,std::numeric_limits<float>::infinity());require(Decode(r.bytes,q,false,context,context).outcome==Outcome::Invalid,"endpoint");});
    test("shape mismatch refused",[&]{auto r=Fixture(q);put(r,0xba,std::uint8_t(1));require(Decode(r.bytes,q,false,context,context).outcome==Outcome::Invalid,"shape");});
    test("nonboolean byte refused",[&]{auto r=Fixture(q);put(r,0xbb,std::uint8_t(2));require(Decode(r.bytes,q,true,context,context).outcome==Outcome::Invalid,"flag");});
    test("start echo mismatch refused",[&]{auto r=Fixture(q);put(r,0x78,99.f);require(Decode(r.bytes,q,false,context,context).outcome==Outcome::Invalid,"echo");});
    test("return/result mismatch refused",[&]{auto r=Fixture(q,.5f);require(Decode(r.bytes,q,false,context,context).outcome==Outcome::Invalid,"return");});
    test("unreviewed contexts never query",[&]{OneSample s;auto c=context;c.reviewed=false;int calls=0;std::array<Reading,2> out;s.arm();require(!s.run(std::span(&q,1),out,[&]{return c;},[&](auto v){++calls;return Fixture(v);})&&calls==0,"gate");});
    test("every required context flag prevents calls",[&]{for(auto member:{&Context::native_phase,&Context::owner_thread,&Context::watch,&Context::cheats_false,&Context::native_chase,&Context::foreground,&Context::controls_released}){OneSample s;auto c=context;c.*member=false;int calls=0;std::array<Reading,2> out;s.arm();require(!s.run(std::span(&q,1),out,[&]{return c;},[&](auto v){++calls;return Fixture(v);})&&calls==0,"required gate");}});
    test("two-query sample runs once",[&]{OneSample s;auto sphere=q;sphere.kind=Kind::Sphere;sphere.radius=8;std::array<Request,2> req{q,sphere};std::array<Reading,2> out;int calls=0;s.arm();auto run=[&]{return s.run(req,out,[&]{return context;},[&](auto v){++calls;return Fixture(v);});};require(run()&&calls==2,"two");require(!run()&&calls==2,"consumed");});
    test("over-budget never queries",[&]{OneSample s;std::array<Request,3> req{q,q,q};std::array<Reading,2> out;int calls=0;s.arm();require(!s.run(req,out,[&]{return context;},[&](auto v){++calls;return Fixture(v);})&&calls==0,"budget");});
    test("world replacement aborts and discards partial",[&]{OneSample s;auto c=context;std::array<Request,2> req{q,q};std::array<Reading,2> out;int calls=0;s.arm();require(!s.run(req,out,[&]{return c;},[&](auto v){++calls;++c.world;return Fixture(v);})&&calls==1&&out[0].outcome==Outcome::Invalid,"world");});
    test("target/thread/frame/camera change never accepts",[&]{for(auto member:{&Context::target,&Context::thread,&Context::frame,&Context::camera}){OneSample s;auto c=context;std::array<Reading,2> out;int calls=0;s.arm();require(!s.run(std::span(&q,1),out,[&]{return c;},[&](auto v){++calls;++(c.*member);return Fixture(v);})&&calls==1,"identity");}});
    test("focus loss between queries aborts",[&]{OneSample s;auto c=context;std::array<Request,2> req{q,q};std::array<Reading,2> out;int calls=0;s.arm();require(!s.run(req,out,[&]{return c;},[&](auto v){++calls;c.foreground=false;return Fixture(v);})&&calls==1,"focus");});
    test("reentrant run cannot rearm or query",[&]{OneSample s;std::array<Reading,2> out,inner;int calls=0;s.arm();require(s.run(std::span(&q,1),out,[&]{return context;},[&](auto v){++calls;require(!s.arm(),"rearm");require(!s.run(std::span(&q,1),inner,[&]{return context;},[&](auto x){++calls;return Fixture(x);}),"nested");return Fixture(v);})&&calls==1,"outer");});
    test("bad second result discards first",[&]{OneSample s;std::array<Request,2> req{q,q};std::array<Reading,2> out;int calls=0;s.arm();require(!s.run(req,out,[&]{return context;},[&](auto v){auto r=Fixture(v);if(++calls==2)put(r,0xac,-1.f);return r;})&&calls==2&&out[0].outcome==Outcome::Invalid,"partial");});
    test("invalid request consumes without query",[&]{OneSample s;auto bad=q;bad.kind=Kind::Sphere;bad.radius=0;std::array<Reading,2> out;int calls=0;s.arm();require(!s.run(std::span(&bad,1),out,[&]{return context;},[&](auto v){++calls;return Fixture(v);})&&!s.pending()&&calls==0,"request");});
    std::printf("%u offline contract scenarios passed; no engine query was invoked.\n",cases);
  } catch(const std::exception& e) {
    std::fprintf(stderr,"FAIL %s\n",e.what());return 1;
  }
}
