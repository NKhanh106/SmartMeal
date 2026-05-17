"use client";

import { useState, useMemo } from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, ChevronUp, ChevronDown } from "lucide-react";
import type { ChatCard, ChatCardResponse } from "../types";

interface RankCardProps {
  card: ChatCard;
  onSubmit: (response: ChatCardResponse) => void;
  isLoading: boolean;
}

interface SortableItemProps {
  id: string;
  label: string;
  icon?: string | null;
  rank: number;
  onMoveUp: () => void;
  onMoveDown: () => void;
  isFirst: boolean;
  isLast: boolean;
}

function SortableItem({
  id,
  label,
  icon,
  rank,
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
}: SortableItemProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`
        flex items-center gap-3 px-3 py-2.5 rounded-xl border-2 bg-white
        ${isDragging ? "border-emerald-400 shadow-md z-10" : "border-slate-200"}
      `}
    >
      {/* Drag handle (desktop) */}
      <div
        {...attributes}
        {...listeners}
        className="text-slate-300 hover:text-slate-500 cursor-grab active:cursor-grabbing hidden sm:block"
      >
        <GripVertical className="h-4 w-4" />
      </div>

      {/* Rank badge */}
      <span className="flex-shrink-0 h-6 w-6 rounded-full bg-emerald-100 text-emerald-700 text-xs font-bold flex items-center justify-center">
        {rank}
      </span>

      {/* Label */}
      <div className="flex items-center gap-2 flex-1 min-w-0">
        {icon && <span className="text-base leading-none">{icon}</span>}
        <span className="text-sm font-medium text-slate-800 truncate">{label}</span>
      </div>

      {/* Mobile up/down buttons */}
      <div className="flex flex-col gap-0.5 sm:hidden">
        <button
          onClick={onMoveUp}
          disabled={isFirst}
          className="p-0.5 rounded text-slate-300 hover:text-slate-500 disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <ChevronUp className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={onMoveDown}
          disabled={isLast}
          className="p-0.5 rounded text-slate-300 hover:text-slate-500 disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <ChevronDown className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

export function RankCard({ card, onSubmit, isLoading }: RankCardProps) {
  const options = card.options || [];
  const [orderedIds, setOrderedIds] = useState<string[]>(
    options.map((o) => o.id)
  );

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      setOrderedIds((items) => {
        const oldIndex = items.indexOf(String(active.id));
        const newIndex = items.indexOf(String(over.id));
        const next = [...items];
        next.splice(oldIndex, 1);
        next.splice(newIndex, 0, String(active.id));
        return next;
      });
    }
  };

  const moveUp = (index: number) => {
    if (index === 0) return;
    setOrderedIds((prev) => {
      const next = [...prev];
      [next[index - 1], next[index]] = [next[index], next[index - 1]];
      return next;
    });
  };

  const moveDown = (index: number) => {
    if (index === orderedIds.length - 1) return;
    setOrderedIds((prev) => {
      const next = [...prev];
      [next[index], next[index + 1]] = [next[index + 1], next[index]];
      return next;
    });
  };

  const handleSubmit = () => {
    onSubmit({
      card_id: card.card_id,
      card_type: card.card_type,
      ranked_ids: orderedIds,
    });
  };

  return (
    <div className="space-y-3">
      <p className="text-xs text-slate-400">
        Kéo thả để sắp xếp thứ tự ưu tiên (trên = ưu tiên cao nhất)
      </p>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={orderedIds}
          strategy={verticalListSortingStrategy}
        >
          <div className="space-y-2">
            {orderedIds.map((id, index) => {
              const opt = options.find((o) => o.id === id)!;
              return (
                <SortableItem
                  key={id}
                  id={id}
                  label={opt.label}
                  icon={opt.icon}
                  rank={index + 1}
                  onMoveUp={() => moveUp(index)}
                  onMoveDown={() => moveDown(index)}
                  isFirst={index === 0}
                  isLast={index === orderedIds.length - 1}
                />
              );
            })}
          </div>
        </SortableContext>
      </DndContext>
      <button
        onClick={handleSubmit}
        disabled={isLoading}
        className="w-full py-2.5 rounded-xl bg-emerald-500 text-white text-sm font-semibold
                   hover:bg-emerald-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isLoading ? "Đang xử lý..." : "Xác nhận thứ tự"}
      </button>
    </div>
  );
}
