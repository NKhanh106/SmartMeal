/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { UserProfile } from '@/types';
import { getUserProfile } from '@/services/mockService';
import { Avatar, AvatarImage, AvatarFallback } from '@/components/ui/avatar';
import { Skeleton } from '@/components/ui/skeleton';

export default function Profile() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getUserProfile().then(data => {
      setProfile(data);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-12 w-1/3" />
        <Card>
          <CardContent className="p-10 space-y-4">
            <Skeleton className="h-24 w-24 rounded-full" />
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-4 w-96" />
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Health Profile</h1>
      
      <div className="grid gap-6 md:grid-cols-3">
        <Card className="md:col-span-1">
          <CardContent className="p-6 flex flex-col items-center text-center">
            <Avatar className="h-32 w-32 mb-4 border-4 border-primary/10">
              <AvatarImage src={profile?.avatar} />
              <AvatarFallback>{profile?.name[0]}</AvatarFallback>
            </Avatar>
            <h2 className="text-xl font-bold">{profile?.name}</h2>
            <p className="text-sm text-muted-foreground">{profile?.email}</p>
            <Button variant="outline" size="sm" className="mt-4">Change Avatar</Button>
          </CardContent>
        </Card>

        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>Physical Information</CardTitle>
            <CardDescription>Used to calculate basic metabolic rate and caloric needs.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="age">Age</Label>
                <Input id="age" defaultValue={profile?.age} type="number" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="gender">Gender</Label>
                <select id="gender" className="w-full p-2 rounded-md border bg-background" defaultValue={profile?.gender}>
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="height">Height (cm)</Label>
                <Input id="height" defaultValue={profile?.height} type="number" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="weight">Weight (kg)</Label>
                <Input id="weight" defaultValue={profile?.weight} type="number" />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Activity Level</Label>
              <p className="text-xs text-muted-foreground mb-2">How much do you move on average?</p>
              <select className="w-full p-2 rounded-md border bg-background" defaultValue={profile?.activityLevel}>
                <option value="sedentary">Sedentary (Little to no exercise)</option>
                <option value="lightly_active">Lightly Active (1-3 days/week)</option>
                <option value="moderately_active">Moderately Active (3-5 days/week)</option>
                <option value="very_active">Very Active (6-7 days/week)</option>
                <option value="extra_active">Extra Active (Athlete/Physical job)</option>
              </select>
            </div>
            <Button className="w-full md:w-auto">Save Profile</Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
