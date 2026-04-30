/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { UserProfile, NutritionGoal, MealLog, DailyRecommendation, WorkoutPlan, ProgressLog } from './types';

export const mockUserProfile: UserProfile = {
  id: 'u1',
  name: 'Nguyễn Văn A',
  email: 'nguyenvana@example.com',
  avatar: 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&q=80&w=150&h=150',
  age: 24,
  gender: 'male',
  height: 175,
  weight: 70,
  activityLevel: 'moderately_active',
  healthGoals: ['Weight Loss', 'Muscle Building', 'Healthy Eating'],
};

export const mockNutritionGoal: NutritionGoal = {
  calories: 2200,
  protein: 150,
  carbs: 250,
  fat: 70,
  water: 2.5,
};

export const mockMealLogs: MealLog[] = [
  {
    id: 'm1',
    timestamp: '2026-04-30T07:30:00Z',
    type: 'breakfast',
    totalCalories: 450,
    totalProtein: 25,
    totalCarbs: 50,
    totalFat: 15,
    items: [
      { id: 'i1', name: 'Oatmeal with Blueberries', calories: 300, protein: 10, carbs: 40, fat: 5 },
      { id: 'i2', name: 'Boiled Egg', calories: 70, protein: 6, carbs: 1, fat: 5 },
      { id: 'i3', name: 'Greek Yogurt', calories: 80, protein: 9, carbs: 9, fat: 5 },
    ],
  },
  {
    id: 'm2',
    timestamp: '2026-04-30T12:00:00Z',
    type: 'lunch',
    totalCalories: 650,
    totalProtein: 40,
    totalCarbs: 60,
    totalFat: 25,
    items: [
      { id: 'i4', name: 'Grilled Chicken Breast', calories: 250, protein: 30, carbs: 0, fat: 5 },
      { id: 'i5', name: 'Brown Rice', calories: 200, protein: 5, carbs: 45, fat: 2 },
      { id: 'i6', name: 'Mixed Salad with Avocado', calories: 200, protein: 5, carbs: 15, fat: 18 },
    ],
  },
];

export const mockDailyRecommendation: DailyRecommendation = {
  id: 'dr1',
  date: '2026-04-30',
  breakfast: 'Scrambled eggs with spinach and whole grain toast',
  lunch: 'Quinoa bowl with roasted vegetables and chickpeas',
  dinner: 'Baked salmon with steamed broccoli and sweet potato',
  snacks: ['Apple with almond butter', 'Mixed nuts'],
  tips: [
    'Drink a glass of water before each meal to aid digestion.',
    'Include protein in every snack to maintain muscle mass.',
    'Avoid screen time 30 minutes before bed for better sleep.'
  ],
};

export const mockWorkoutPlan: WorkoutPlan[] = [
  {
    id: 'w1',
    day: 'Monday',
    type: 'Push Day (Strength)',
    totalEstimatedCalories: 450,
    items: [
      { id: 'wi1', name: 'Bench Press', sets: 4, reps: 8, caloriesBurned: 120 },
      { id: 'wi2', name: 'Overhead Press', sets: 3, reps: 10, caloriesBurned: 100 },
      { id: 'wi3', name: 'Lateral Raises', sets: 3, reps: 15, caloriesBurned: 50 },
      { id: 'wi4', name: 'Triceps Pushdown', sets: 3, reps: 12, caloriesBurned: 60 },
    ],
  },
  {
    id: 'w2',
    day: 'Tuesday',
    type: 'Pull Day (Hypertrophy)',
    totalEstimatedCalories: 400,
    items: [
      { id: 'wi5', name: 'Pull Ups', sets: 4, reps: 6, caloriesBurned: 110 },
      { id: 'wi6', name: 'Barbell Rows', sets: 3, reps: 10, caloriesBurned: 120 },
      { id: 'wi7', name: 'Bicep Curls', sets: 3, reps: 12, caloriesBurned: 70 },
    ],
  },
];

export const mockProgressLogs: ProgressLog[] = [
  { date: '2026-04-24', weight: 72.0, caloriesIn: 2100, caloriesOut: 2400 },
  { date: '2026-04-25', weight: 71.8, caloriesIn: 2200, caloriesOut: 2500 },
  { date: '2026-04-26', weight: 71.5, caloriesIn: 1900, caloriesOut: 2300 },
  { date: '2026-04-27', weight: 71.2, caloriesIn: 2300, caloriesOut: 2600 },
  { date: '2026-04-28', weight: 70.8, caloriesIn: 2150, caloriesOut: 2450 },
  { date: '2026-04-29', weight: 70.5, caloriesIn: 2000, caloriesOut: 2350 },
  { date: '2026-04-30', weight: 70.0, caloriesIn: 2200, caloriesOut: 2550 },
];
