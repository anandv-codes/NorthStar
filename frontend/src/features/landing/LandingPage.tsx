import { PublicNavBar } from "./PublicNavBar";
import { Footer } from "./Footer";
import { Hero } from "./sections/Hero";
import { ProductShowcase } from "./sections/ProductShowcase";
import { HowItWorks } from "./sections/HowItWorks";
import { FeatureGrid } from "./sections/FeatureGrid";
import { Pricing } from "./sections/Pricing";
import { FAQ } from "./sections/FAQ";
import { FinalCTA } from "./sections/FinalCTA";

export function LandingPage() {
  return (
    <div className="min-h-screen bg-white">
      <PublicNavBar />
      <main>
        <Hero />
        <ProductShowcase />
        <HowItWorks />
        <FeatureGrid />
        <Pricing />
        <FAQ />
        <FinalCTA />
      </main>
      <Footer />
    </div>
  );
}
