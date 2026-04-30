/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { motion } from 'motion/react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { 
  ShieldCheck, 
  Zap, 
  Smartphone, 
  BarChart3, 
  CheckCircle2,
  ChefHat,
  Dumbbell
} from 'lucide-react';

export default function Landing() {
  return (
    <div className="flex flex-col min-h-screen bg-white text-slate-900">
      {/* Navbar */}
      <header className="px-4 lg:px-6 h-16 flex items-center border-b sticky top-0 bg-white/80 backdrop-blur-md z-40">
        <Link className="flex items-center justify-center" to="/">
          <div className="h-8 w-8 bg-primary rounded-lg flex items-center justify-center mr-2">
            <Zap className="h-5 w-5 text-white" />
          </div>
          <span className="font-bold text-xl tracking-tight">SmartMeal</span>
        </Link>
        <nav className="ml-auto flex gap-4 sm:gap-6 items-center">
          <Link className="text-sm font-medium hover:text-primary transition-colors" to="/login">
            Login
          </Link>
          <Button asChild size="sm">
            <Link to="/register">Get Started</Link>
          </Button>
        </nav>
      </header>

      <main className="flex-1">
        {/* Hero Section */}
        <section className="w-full py-12 md:py-24 lg:py-32 xl:py-48 bg-gradient-to-b from-blue-50 to-white overflow-hidden relative">
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="container px-4 md:px-6 mx-auto relative z-10"
          >
            <div className="flex flex-col items-center space-y-4 text-center">
              <div className="inline-block rounded-full bg-blue-100 px-3 py-1 text-sm font-semibold text-blue-600 mb-2">
                Your Personal AI Nutritionist
              </div>
              <h1 className="text-4xl font-extrabold tracking-tighter sm:text-5xl md:text-6xl lg:text-7xl">
                Eat Smarter, <span className="text-primary">Live Better</span>
              </h1>
              <p className="mx-auto max-w-[700px] text-slate-600 md:text-xl/relaxed lg:text-base/relaxed xl:text-xl/relaxed">
                SmartMeal uses AI to analyze your meals, track your nutrients, and suggest 
                personalized workout plans. All in one simple dashboard.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 pt-4">
                <Button asChild size="lg" className="rounded-full h-12 px-8 text-lg shadow-lg">
                  <Link to="/register">Start for Free</Link>
                </Button>
                <Button variant="outline" size="lg" className="rounded-full h-12 px-8 text-lg">
                  Learn More
                </Button>
              </div>
            </div>
          </motion.div>
          
          {/* Abstract blobs */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-full w-full pointer-events-none overflow-hidden">
            <div className="absolute top-0 right-0 w-96 h-96 bg-blue-200/40 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
            <div className="absolute bottom-0 left-0 w-80 h-80 bg-primary/20 rounded-full blur-3xl translate-y-1/2 -translate-x-1/2" />
          </div>
        </section>

        {/* Features Section */}
        <section className="w-full py-24 bg-slate-50">
          <div className="container px-4 md:px-6 mx-auto">
            <div className="grid gap-12 lg:grid-cols-3">
              {[
                { 
                  icon: Smartphone, 
                  title: 'Snap & Analyze', 
                  desc: 'Simply take a photo of your meal and our AI will automatically detect ingredients and calculate macros.' 
                },
                { 
                  icon: BarChart3, 
                  title: 'Data-Driven Insights', 
                  desc: 'Visualize your progress with detailed charts and understand your metabolic trends over time.' 
                },
                { 
                  icon: Dumbbell, 
                  title: 'Personalized Workout', 
                  desc: 'Get workout routines tailored to your energy intake and fitness level, designed by top coaches.' 
                },
              ].map((feature, i) => (
                <motion.div 
                  key={i}
                  initial={{ opacity: 0, scale: 0.95 }}
                  whileInView={{ opacity: 1, scale: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.1 }}
                  className="flex flex-col items-center text-center p-6 bg-white rounded-3xl shadow-sm border border-slate-100 hover:shadow-md transition-shadow"
                >
                  <div className="h-16 w-16 bg-blue-50 rounded-2xl flex items-center justify-center mb-6">
                    <feature.icon className="h-8 w-8 text-primary" />
                  </div>
                  <h3 className="text-xl font-bold mb-3">{feature.title}</h3>
                  <p className="text-slate-600 leading-relaxed">{feature.desc}</p>
                </motion.div>
              ))}
            </div>
          </div>
        </section>
      </main>

      <footer className="w-full py-12 border-t bg-slate-900 text-slate-400">
        <div className="container px-4 md:px-6 mx-auto">
          <div className="grid gap-8 lg:grid-cols-4">
            <div className="space-y-4">
              <div className="flex items-center">
                <Zap className="h-6 w-6 text-primary mr-2" />
                <span className="font-bold text-white text-xl">SmartMeal</span>
              </div>
              <p className="text-sm">Empowering health through data and AI analysis.</p>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Product</h4>
              <ul className="space-y-2 text-sm">
                <li><Link to="#">Features</Link></li>
                <li><Link to="#">Pricing</Link></li>
                <li><Link to="#">Reviews</Link></li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Company</h4>
              <ul className="space-y-2 text-sm">
                <li><Link to="#">About</Link></li>
                <li><Link to="#">Blog</Link></li>
                <li><Link to="#">Careers</Link></li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Legal</h4>
              <ul className="space-y-2 text-sm">
                <li><Link to="#">Privacy</Link></li>
                <li><Link to="#">Terms</Link></li>
              </ul>
            </div>
          </div>
          <div className="mt-12 pt-8 border-t border-slate-800 text-center text-xs">
            © 2026 SmartMeal Inc. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  );
}
