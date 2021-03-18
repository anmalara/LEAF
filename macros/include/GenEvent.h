#pragma once

#include <TString.h>
#include <TH1F.h>
#include <map>
#include <TTreeReader.h>
#include <TTreeReaderValue.h>

#include "include/Met.h"
#include "include/GenParticle.h"
#include "include/GenJet.h"
#include "include/Event.h"

using namespace std;

// Container class for all quantities
class GenEvent : public Event{

public:
  // Constructors, destructor
  GenEvent();
  ~GenEvent();

  void clear();
  void reset();

  Met* genmet;
  Met* genmet_invis;
  vector<GenParticle>* genparticles_hard;
  vector<GenParticle>* genparticles_final;
  vector<GenParticle>* genparticles_visibletaus;
  vector<GenJet>* genjets;
};