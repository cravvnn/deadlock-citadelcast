#pragma once
#include "hero_composition.hpp"
#include <cstring>

namespace hero {
// Publishes only the seven common pose/lens floats of a positively owned data
// camera. Call from its owner update, before native post-update/render readers.
// Unknown ownership or invalid input leaves the entire destination unchanged.
inline bool WriteNativePose(float* output,const follow::Pose& pose,float entry_fov,bool owned_and_allowed){
    if(!owned_and_allowed || !output || !follow::Finite(pose) || !std::isfinite(entry_fov) || entry_fov<=1 || entry_fov>=179)return false;
    std::array<float,7> value{};
    for(unsigned n=0;n<6;++n){value[n]=static_cast<float>(pose[n]);if(!std::isfinite(value[n]))return false;}
    value[6]=entry_fov;
    std::memcpy(output,value.data(),sizeof(value));return true;
}
}
