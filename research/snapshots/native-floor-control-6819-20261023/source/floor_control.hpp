#pragma once
// Independent request/expected-result policy; no engine access or camera output.
#include "query_contract.hpp"
namespace floor_control {
using collision_contract::Vec3;
using collision_contract::Request;
inline bool Requests(const Vec3& root,std::array<Request,2>& out){
    if(!collision_contract::Finite(root))return false;
    Vec3 start=root,end=root;start[2]+=64;end[2]-=128;
    out={Request{start,end,collision_contract::Kind::Line,0},
         Request{start,end,collision_contract::Kind::Sphere,8}};
    return start[2]>root[2]&&end[2]<root[2]&&
        collision_contract::Valid(out[0])&&collision_contract::Valid(out[1]);
}
inline bool ContactPair(const std::array<collision_contract::Reading,2>& readings){
    for(const auto& r:readings)if(r.outcome!=collision_contract::Outcome::Contact||
        r.raw_start_solid!=0||!std::isfinite(r.fraction)||r.fraction<=0||r.fraction>=1)return false;
    return true;
}
}
