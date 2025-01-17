#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wattributes"
#pragma GCC diagnostic ignored "-Wdeprecated-declarations"
#include <TFile.h>
#include <TTree.h>
#include "DataFormats/FWLite/interface/Handle.h"
#include "DataFormats/FWLite/interface/Event.h"
#include "DataFormats/RecoCandidate/interface/RecoCandidate.h"
#include "DataFormats/HepMCCandidate/interface/GenParticle.h"
#include "DataFormats/METReco/interface/GenMET.h"
#include "DataFormats/JetReco/interface/GenJet.h"
#include "FWCore/FWLite/interface/FWLiteEnabler.h"
#include "SimDataFormats/GeneratorProducts/interface/GenEventInfoProduct.h"
#include <iostream>
#include "Analyzer/include/GenEvent.h"
#include "Analyzer/include/Met.h"
#include "Analyzer/include/Particle.h"
#include "Analyzer/include/GenParticle.h"
#include "Analyzer/include/GenJet.h"
#include "Analyzer/include/useful_functions.h"
#include "Analyzer/include/constants.h"
#include <TSystem.h>
#include <sys/stat.h>
#include <experimental/filesystem>
#pragma GCC diagnostic pop

using namespace std;

// Example usage:
//
// Tuplizer /pnfs/psi.ch/cms/trivcat/store/user/areimers/GENSIM/LQDM/LQDM_MLQ1400_MX660_MDM600_L1p0/GENSIM_1.root /scratch/areimers/Tuples/LQDM/GENSIM/test.root


TLorentzVector p4sumvis(vector<GenParticle> particles);
vector<reco::GenParticle> finalDaughters(reco::GenParticle particle, vector<reco::GenParticle> daus);


int main(int argc, char* argv[]){

  FWLiteEnabler::enable();

  if(argc != 3) throw runtime_error("Expected exactly two arguments. Usage: ./main <infilename> <outfilename>");
  TString director = "root://t3dcachedb03.psi.ch:1094/";
  string inarg  = argv[1];
  string outarg = argv[2];

  TString infilename = (TString)inarg;
  TString outfilename = (TString)outarg;
  cout << green << "--> Tuplizing file: " << infilename << reset << endl;
  cout << green << "--> Output file will be: " << outfilename << reset << endl;
  TFile* infile = TFile::Open(infilename, "READ");

  const vector<int> npids = get_npids();
  GenEvent event;

  TFile* outfile = new TFile(outfilename, "RECREATE");
  TTree* tree = new TTree("AnalysisTree", "AnalysisTree");

  tree->Branch("Events", &event);

  fwlite::Handle<std::vector<reco::GenParticle> > handle_gps;
  // fwlite::Handle<vector<reco::GenMET> >           handle_met;
  fwlite::Handle<vector<reco::GenJet> >           handle_genjets;
  fwlite::Handle<GenEventInfoProduct>             handle_geninfo;


  fwlite::Event ev(infile);
  int idx = 0;
  for( ev.toBegin(); ! ev.atEnd(); ++ev) {
    if(((idx+1) % 500 == 0) || idx == 0) cout << green << "    --> At event: " << idx+1 << reset << endl;
    // cout << "=========== NEW EVENT" << endl;
    handle_gps    .getByLabel(ev, "genParticles");
    // handle_met    .getByLabel(ev, "genMetTrue");
    handle_genjets.getByLabel(ev, "ak4GenJets");
    handle_geninfo.getByLabel(ev, "generator");
    // const std::vector<reco::GenMET, std::allocator<reco::GenMET>>*           gm  = handle_met.product();
    const std::vector<reco::GenParticle, std::allocator<reco::GenParticle>>* gps = handle_gps.product();
    const std::vector<reco::GenJet, std::allocator<reco::GenJet>>*           gjs = handle_genjets.product();
    const GenEventInfoProduct*                                               gif = handle_geninfo.product();


    // Do GenParticles
    // ===============

    GenParticle p4suminvis;
    for(size_t i=0; i<gps->size(); i++){
      int id = abs(gps->at(i).pdgId());

      // This selects all particles in their final form (i.e. after radiation, but before potential decay, to compare to particles from hard process)
      bool isfinal      = gps->at(i).isLastCopy();

      //This selects all final-state particles (i.e. no intermediate particles that decay further)
      bool isfinalstate = gps->at(i).status() == 1;

      bool ishard  = gps->at(i).isHardProcess();
      bool keepfinal = false;
      bool finalstate_invis = false;
      if(isfinal){
        //keep, if final particle is b, t, tau, or nutau
        for(size_t j=0; j<npids.size(); j++){
          if(id == npids[j]) keepfinal = true;
        }
        if(id == 5 || id == 6 || id == 15 || id == 16) keepfinal = true;
      }

      // find all (hopefully) invisible particles in final state
      if(isfinalstate){
        for(size_t j=0; j<chiids.size(); j++){
          if(id == chiids[j]) finalstate_invis = true;
        }
        if(id == 12 || id == 14 || id == 16) finalstate_invis = true;
      }

      // this will be written out if we keep this particle
      GenParticle p;
      p.set_pt(gps->at(i).pt());
      p.set_eta(gps->at(i).eta());
      p.set_phi(gps->at(i).phi());
      p.set_m(gps->at(i).mass());
      p.set_pdgid(gps->at(i).pdgId());
      p.set_ndaughters(gps->at(i).numberOfDaughters());
      event.genparticles_all->emplace_back(p);

      if(keepfinal){
        // event.genparticles_final->emplace_back(p);
        // save visible daughters of final taus (not only from hard-process-taus)
        if(id == 15){
          vector<reco::GenParticle> dummydaus = {};
          vector<reco::GenParticle> taudaus = finalDaughters(gps->at(i), dummydaus);
          vector<GenParticle> tds = {};
          for(size_t j=0; j<taudaus.size(); j++){
            GenParticle thisp;
            thisp.set_p4(taudaus[j].pt(), taudaus[j].eta(), taudaus[j].phi(), taudaus[j].mass());
            thisp.set_pdgid(taudaus[j].pdgId());
            thisp.set_ndaughters(taudaus[j].numberOfDaughters());
            tds.emplace_back(thisp);
          }
          TLorentzVector p4vis = p4sumvis(tds);

          GenParticle taudaughters_visible;
          taudaughters_visible.set_p4(p4vis);
          taudaughters_visible.set_pdgid(gps->at(i).pdgId());
          taudaughters_visible.set_ndaughters((int)tds.size());
          event.genparticles_visibletaus->emplace_back(taudaughters_visible);
        }
      }
      // if(ishard){
      //   event.genparticles_hard->emplace_back(p);
      // }
      if(finalstate_invis){
        TLorentzVector p4current = p4suminvis.p4();
        p4current += p.p4();
        p4suminvis.set_p4(p4current);
          // cout << "adding this particle of ID " << id << " with pT " << p.pt() << " to MET. Now: " << p4suminvis.pt() << endl;
      }
    }

    // Do GenJets
    // ==========

    for(size_t i=0; i<gjs->size(); i++){
      GenJet gj;
      gj.set_p4(gjs->at(i).pt(), gjs->at(i).eta(), gjs->at(i).phi(), gjs->at(i).mass());
      // cout << "genjet pt: " << gj.pt() << endl;
      // remove NP particles that have been clustered into a jet from the jet. Only happens for DM.
      int n_const_removed = 0;
      for(size_t j=0; j<gjs->at(i).getGenConstituents().size(); j++){
        int id = abs(gjs->at(i).getGenConstituents().at(j)->pdgId());
        for(size_t k=0; k<npids.size(); k++){
          if(id == npids[k]){

            //Get NP 4-momentum
            GenParticle np;
            np.set_p4(gjs->at(i).getGenConstituents().at(j)->pt(), gjs->at(i).getGenConstituents().at(j)->eta(), gjs->at(i).getGenConstituents().at(j)->phi(), gjs->at(i).getGenConstituents().at(j)->mass());

            //Remove np 4-momentum
            // cout << "jet pt before: " << gj.pt() << endl;
            gj.set_p4(gj.p4() - np.p4());
            n_const_removed++;
            // cout << "Removed particle with ID " << id << " and pt " << np.pt() << " from a genJet." << endl;
            // cout << "jet pt after:  " << gj.pt() << endl;
          }
        }
      }
      gj.set_n_constituents(gjs->at(i).getGenConstituents().size() - n_const_removed);

      // save only genjets with at least 5GeV and |eta| < 5
      if(gj.pt() < 5 || fabs(gj.eta()) > 5.) continue;
      event.genjets->emplace_back(gj);
      // cout << "added genjet with pt: " << gj.pt() << endl;
    }

    // Do GenMET
    // =========

    // The p4suminvis is safer than just gen-met. on gen-level, gen-met is sometimes buggy and does not recognize DM as MET.
    // event.genmet->set_pt(gm->at(0).pt());
    // event.genmet->set_phi(gm->at(0).phi());
    event.genmet->set_pt(p4suminvis.pt());
    event.genmet->set_phi(p4suminvis.phi());

    // TODO This is commented in the GenEvent -- probably don't need a separate Gensim analyzer anymore?
    // event.genmet_invis->set_pt(p4suminvis.pt());
    // event.genmet_invis->set_phi(p4suminvis.phi());
    // cout << "sum invis: " << p4suminvis.pt() << endl;


    // Do weight
    // =========
    event.weight = gif->weight();
    tree->Fill();
    event.reset();
    idx ++;
  }

  event.clear();
  tree->Write();
  outfile->Close();
  cout << green << "--> Successfully finished tuplization." << reset << endl;
}







TLorentzVector p4sumvis(vector<GenParticle> particles){
  TLorentzVector result;
  for(size_t i=0; i<particles.size(); i++){
    int id = abs(particles.at(i).pdgid());
    if(id != 12 && id != 14 && id != 16) result += particles.at(i).p4();
  }
  return result;
}

vector<reco::GenParticle> finalDaughters(const reco::GenParticle particle, vector<reco::GenParticle> daus){
  //   //Fills daughters with all the daughters of particle recursively.
  vector<reco::GenParticle> daughters = daus;
  if(particle.numberOfDaughters()==0) daughters.emplace_back(particle);
  else{
    bool foundDaughter = false;
    for(size_t i=0; i<particle.numberOfDaughters(); i++){
      const reco::GenParticle* dau = ((reco::GenParticle*)(particle.daughter(i)));
      if(dau->status()>=1){
        daughters = finalDaughters( *dau, daughters );
        foundDaughter = true;
      }
    }
    if(!foundDaughter) daughters.emplace_back(particle);
  }
  return daughters;
}
