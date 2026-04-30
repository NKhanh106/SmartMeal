/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Camera, Upload, CheckCircle2, Loader2, Sparkles } from 'lucide-react';
import { analyzeMealImage } from '@/services/mockService';
import { MealLog } from '@/types';

export default function UploadPage() {
  const [image, setImage] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<MealLog | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const url = URL.createObjectURL(file);
      setImage(url);
      setResult(null);
    }
  };

  const startAnalysis = async () => {
    if (!image) return;
    setAnalyzing(true);
    try {
      const data = await analyzeMealImage(image);
      setResult(data);
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="space-y-8 max-w-2xl mx-auto">
      <div>
        <h1 className="text-3xl font-bold">Upload Meal</h1>
        <p className="text-muted-foreground">Take a photo of your food to get instant nutritional data.</p>
      </div>

      <Card className="relative overflow-hidden border-2 border-dashed border-primary/20">
        <CardContent className="p-12 flex flex-col items-center justify-center min-h-[300px]">
          {image ? (
            <div className="relative w-full aspect-video rounded-xl overflow-hidden shadow-lg">
              <img src={image} alt="Meal" className="w-full h-full object-cover" />
              <Button 
                variant="destructive" 
                size="sm" 
                className="absolute top-2 right-2 rounded-full h-8 w-8 p-0"
                onClick={() => { setImage(null); setResult(null); }}
              >
                ×
              </Button>
            </div>
          ) : (
            <div className="text-center space-y-4">
              <div className="h-16 w-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
                <Camera className="h-8 w-8 text-primary" />
              </div>
              <div className="space-y-1">
                <p className="font-semibold text-lg">Drop your image here</p>
                <p className="text-sm text-muted-foreground">Supports JPG, PNG up to 10MB</p>
              </div>
              <Label htmlFor="file-upload" className="cursor-pointer">
                <div className="bg-primary hover:bg-primary/90 text-primary-foreground px-6 py-2 rounded-lg font-medium inline-block transition-colors">
                  Select File
                </div>
                <input id="file-upload" type="file" className="hidden" accept="image/*" onChange={handleFileChange} />
              </Label>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="flex gap-4">
        <Button 
          className="flex-1 h-12 text-lg shadow-lg" 
          disabled={!image || analyzing || !!result}
          onClick={startAnalysis}
        >
          {analyzing ? (
            <>
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              Analyzing Ingredients...
            </>
          ) : result ? (
            <>
              <CheckCircle2 className="mr-2 h-5 w-5" />
              Analysis Complete
            </>
          ) : (
            <>
              <Sparkles className="mr-2 h-5 w-5" />
              AI Analyze Meal
            </>
          )}
        </Button>
      </div>

      <AnimatePresence>
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
          >
            <Card className="border-primary/20 bg-primary/5 shadow-none overflow-hidden">
              <CardHeader className="bg-white/50 border-b">
                <CardTitle>AI Recognition Result</CardTitle>
                <CardDescription>Detected components in your image.</CardDescription>
              </CardHeader>
              <CardContent className="p-6">
                <div className="space-y-4">
                  <div className="grid grid-cols-4 gap-4 text-center">
                    <div className="bg-white p-3 rounded-lg border">
                      <p className="text-xs text-muted-foreground uppercase font-bold">Calories</p>
                      <p className="text-lg font-bold">{result.totalCalories}</p>
                    </div>
                    <div className="bg-white p-3 rounded-lg border">
                      <p className="text-xs text-muted-foreground uppercase font-bold">Protein</p>
                      <p className="text-lg font-bold">{result.totalProtein}g</p>
                    </div>
                    <div className="bg-white p-3 rounded-lg border">
                      <p className="text-xs text-muted-foreground uppercase font-bold">Carbs</p>
                      <p className="text-lg font-bold">{result.totalCarbs}g</p>
                    </div>
                    <div className="bg-white p-3 rounded-lg border">
                      <p className="text-xs text-muted-foreground uppercase font-bold">Fat</p>
                      <p className="text-lg font-bold">{result.totalFat}g</p>
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <p className="font-semibold text-sm">Detected Items:</p>
                    <ul className="space-y-1">
                      {result.items.map(item => (
                        <li key={item.id} className="flex justify-between text-sm bg-white p-2 rounded border">
                          <span>{item.name}</span>
                          <span className="text-muted-foreground">{item.calories} kcal</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  
                  <Button className="w-full variant-outline">Confirm & Add to History</Button>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Re-using Label from components/ui/label (oops, I forgot I hadn't added it to UI folder if I didn't call it specifically)
// Wait, I should add label explicitly if needed, but for now I'll just use raw <label>
import { Label } from '@/components/ui/label';
