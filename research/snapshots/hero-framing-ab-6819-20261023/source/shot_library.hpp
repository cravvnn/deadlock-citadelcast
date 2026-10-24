#pragma once
#include "walker_shot.hpp"
#include <cstring>
namespace walker {
struct Shot { const char* id;const char* name;double start,end,duration;bool reverse;const char* carrier;const char* hash; };
inline constexpr std::array<Shot,4> kShots={{
  {"walker","Walker original",0.0,14.125,14.125,false,"walker-shot.kv","f059f0df190f082fff729acabb07d6eae20c8043b8ff04d895e09f052e33f189"},
  {"walker-reverse","Walker return",0.0,14.125,14.125,true,"walker-reverse.kv","021039853bd92fb94a01fbbbbb0b264605cd333c0a241d0e5f8bff5f684cff13"},
  {"bank-sweep","Walker bank sweep",3.078125,11.015625,7.9375,false,"bank-sweep.kv","666acf3149296dc65b09cea9949b0eb81244b22626962f3c5ecd8f68e535d0fa"},
  {"arrival","Walker arrival",0.0,3.078125,3.078125,false,"arrival.kv","5be27f2105fefed0cd3a1d8ab3a40eea143d74b79bc1723baf27382ec8e90d44"},
}};
inline const Shot* FindShot(const char* id) {
  if(!id)return nullptr;for(const auto& shot:kShots)if(std::strcmp(shot.id,id)==0)return &shot;return nullptr;
}
inline Pose EvaluateShot(const Shot& shot,double time) {
  time=std::clamp(time,0.0,shot.duration);
  return Evaluate(shot.reverse?shot.end-time:shot.start+time);
}
} // namespace walker
