#pragma once
// Independent OFFLINE boundary. There are no engine pointers, calls, process
// access or camera writes here. A future binding must supply qualified context;
// the synthetic identity token below is NOT a discovered native world epoch.
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <span>

namespace collision_contract {
using Vec3=std::array<float,3>;
enum class Kind:std::uint8_t { Line=0, Sphere=1 };
enum class Outcome { Invalid, NoContact, Contact };
struct Request { Vec3 start{},end{}; Kind kind=Kind::Line; float radius=0; };
struct Context {
    std::uint64_t world=0, target=0, camera=0, thread=0, frame=0;
    bool reviewed=false, native_phase=false, owner_thread=false, watch=false;
    bool cheats_false=false, native_chase=false, foreground=false, controls_released=false;
    bool valid()const {
        return world && target && camera && thread && frame && reviewed && native_phase &&
            owner_thread && watch && cheats_false && native_chase && foreground && controls_released;
    }
    bool same(const Context& x)const {
        return valid() && x.valid() && world==x.world && target==x.target &&
            camera==x.camera && thread==x.thread && frame==x.frame;
    }
};
struct Reading {
    Outcome outcome=Outcome::Invalid;
    const char* reason="not measured";
    Vec3 start{},end{};
    float fraction=0;
    std::uint8_t raw_start_solid=0,raw_exact_point=0;
};
inline bool Finite(const Vec3& v) { for(float n:v)if(!std::isfinite(n))return false;return true; }
inline bool Valid(const Request& q) {
    // Bounds belong to this diagnostic design, not measured Deadlock limits.
    if(!Finite(q.start)||!Finite(q.end)||!std::isfinite(q.radius)||q.radius<0||q.radius>64)return false;
    for(int i=0;i<3;++i)if(std::abs(q.start[i])>1e6f||std::abs(q.end[i])>1e6f)return false;
    return (q.kind==Kind::Line&&q.radius==0)||(q.kind==Kind::Sphere&&q.radius>0);
}
template<class T>T Read(std::span<const std::byte> bytes,std::size_t at) {
    T out{};std::memcpy(&out,bytes.data()+at,sizeof(T));return out;
}
inline Reading Decode(std::span<const std::byte> bytes,const Request& q,bool native_hit,
                      const Context& before,const Context& after) {
    Reading r;
    auto refuse=[&](const char* why){r.reason=why;return r;};
    if(!before.same(after))return refuse("unqualified or changed context");
    if(!Valid(q))return refuse("invalid request");
    if(bytes.size()!=0xc0)return refuse("wrong result extent");
    r.start=Read<Vec3>(bytes,0x78);r.end=Read<Vec3>(bytes,0x84);
    r.fraction=Read<float>(bytes,0xac);
    const auto kind=Read<std::uint8_t>(bytes,0xba);
    r.raw_start_solid=Read<std::uint8_t>(bytes,0xbb);
    r.raw_exact_point=Read<std::uint8_t>(bytes,0xbc);
    if(kind!=static_cast<std::uint8_t>(q.kind))return refuse("wrong shape tag");
    if(!Finite(r.start)||!Finite(r.end)||!std::isfinite(r.fraction)||r.fraction<0||r.fraction>1)
        return refuse("invalid numeric result");
    if(r.raw_start_solid>1||r.raw_exact_point>1)return refuse("nonboolean result flag");
    // TraceShape copies input start bytes; compare exactly, not an invented
    // coordinate tolerance. No raw hit-entity/body/shape pointers are consumed.
    if(std::memcmp(r.start.data(),q.start.data(),sizeof(Vec3)))return refuse("start echo differs");
    const bool hit=r.fraction<1 || r.raw_start_solid!=0;
    if(hit!=native_hit)return refuse("return value and result disagree");
    r.outcome=hit?Outcome::Contact:Outcome::NoContact;
    r.reason=hit?"contact under this query/filter only":"no contact under this query/filter only";
    return r;
}

struct RawResult { std::array<std::byte,0xc0> bytes{};bool hit=false; };
// Manually armed, one same-frame batch, two comparison queries at most. Invalid
// readings discard the whole batch. No retry or rearm during a query callback.
class OneSample {
    bool busy_=false,armed_=false;
public:
    bool arm(){if(busy_||armed_)return false;armed_=true;return true;}
    bool pending()const{return armed_;}
    template<class Observe,class Query>
    bool run(std::span<const Request> requests,std::array<Reading,2>& output,
             Observe observe,Query query) {
        output={};
        if(busy_||!armed_)return false;
        armed_=false;
        if(requests.empty()||requests.size()>2)return false;
        for(const auto& q:requests)if(!Valid(q))return false;
        busy_=true;struct Done{bool& busy;~Done(){busy=false;}}done{busy_};
        const auto initial=observe();
        if(!initial.valid())return false;
        std::array<Reading,2> staged{};
        for(std::size_t i=0;i<requests.size();++i){
            const auto before=observe();if(!initial.same(before))return false;
            const RawResult raw=query(requests[i]);
            const auto after=observe();
            if(!initial.same(after))return false;
            staged[i]=Decode(raw.bytes,requests[i],raw.hit,before,after);
            if(staged[i].outcome==Outcome::Invalid)return false;
        }
        if(!initial.same(observe()))return false;
        output=staged;return true;
    }
};
}
