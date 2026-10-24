#pragma once
// Native-equivalent primitive/filter bytes. The injected function is a fake in
// tests; the separately pinned adapter is the only place with an engine address.
#include "query_contract.hpp"
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
namespace wall_query {
using collision_contract::Request;
using collision_contract::Vec3;
template<class T,class Bytes>void Put(Bytes& b,std::size_t at,const T& x){std::memcpy(b.data()+at,&x,sizeof(x));}
struct alignas(8) Shape {std::array<std::byte,0x30> bytes{};};
struct alignas(8) Filter {std::array<std::byte,0x48> bytes{};};
inline Shape MakeShape(const Request& q){
    Shape s;Put(s.bytes,0xc,q.radius);Put(s.bytes,0x28,static_cast<std::uint8_t>(q.kind));return s;
}
inline Filter MakeFilter(std::uintptr_t native_table){
    Filter f;Put(f.bytes,0,native_table);
    Put(f.bytes,8,std::uint64_t(0x20000000001081));
    Put(f.bytes,0x10,std::uint64_t(0x14000000202c0000));
    for(std::size_t at:{0x20u,0x24u,0x28u,0x2cu})Put(f.bytes,at,std::uint32_t(0xffffffff));
    Put(f.bytes,0x34,std::uint16_t(0xffff));
    // First test is STATIC objects only. Native TraceShape skips its broader
    // entity-mask normalizer for object-set1; moving-object coverage comes later.
    Put(f.bytes,0x37,std::uint8_t(1));Put(f.bytes,0x38,std::uint8_t(3));
    Put(f.bytes,0x39,std::uint8_t(0x49)); // Native default bits; reserved high bit is zero.
    return f; // +0x40 false: closest hit, no ShouldHitEntity iteration callback.
}
struct alignas(16) Scratch {
    static constexpr std::uint64_t Guard=0x912e7a06d5b3c84full;
    std::array<std::uint64_t,2> prefix{Guard,Guard};
    alignas(16) std::array<std::byte,0xc0> bytes{};
    std::array<std::uint64_t,2> suffix{Guard,Guard};
    bool intact()const{return prefix[0]==Guard&&prefix[1]==Guard&&suffix[0]==Guard&&suffix[1]==Guard;}
};
static_assert(sizeof(Shape)==0x30&&alignof(Shape)==8);
static_assert(sizeof(Filter)==0x48&&alignof(Filter)==8);
static_assert(offsetof(Scratch,bytes)==16&&alignof(Scratch)==16);
struct Invocation {bool called=false,guard_ok=false;collision_contract::RawResult result;};
template<class Native>Invocation Invoke(Native native,void* holder,std::uintptr_t filter_table,const Request& q){
    Invocation out;
    if(!holder||!filter_table||!collision_contract::Valid(q))return out;
    auto shape=MakeShape(q);auto filter=MakeFilter(filter_table);
    const auto expected_shape=shape.bytes;
    const auto expected_filter=filter.bytes;Scratch scratch;
    out.called=true;
    out.result.hit=native(holder,static_cast<const void*>(&shape),q.start.data(),q.end.data(),
                         static_cast<void*>(&filter),static_cast<void*>(scratch.bytes.data()));
    out.guard_ok=scratch.intact()&&shape.bytes==expected_shape&&filter.bytes==expected_filter;
    if(out.guard_ok)out.result.bytes=scratch.bytes;
    return out;
}
// The diagnostic follows the visible native camera bearing and extends64units
// past its current eye. Radius8 is a comparison primitive, not a lens envelope.
inline bool Requests(const Vec3& root,const Vec3& eye,std::array<Request,2>& out){
    if(!collision_contract::Finite(root)||!collision_contract::Finite(eye))return false;
    Vec3 focus=root;focus[2]+=48;
    double squared=0;for(unsigned i=0;i<3;++i)squared+=double(eye[i]-focus[i])*(eye[i]-focus[i]);
    const double distance=std::sqrt(squared);
    if(!std::isfinite(distance)||distance<16||distance>960)return false;
    Vec3 end{};for(unsigned i=0;i<3;++i)end[i]=static_cast<float>(eye[i]+64*(eye[i]-focus[i])/distance);
    out={Request{focus,end,collision_contract::Kind::Line,0},Request{focus,end,collision_contract::Kind::Sphere,8}};
    return collision_contract::Valid(out[0])&&collision_contract::Valid(out[1]);
}
}
