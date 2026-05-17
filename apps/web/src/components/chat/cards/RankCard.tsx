"use client";

import { useState } from "react";
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
  verticalListSortingStrategy,
  useSortable,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, ChevronUp, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CardOption } from "@/components/chatbot/types";

interface SortableItemProps {
  id: string;
  option: CardOption;
  index: number;
  onMoveUp: (index: number) => void;
  onMoveDown: (index: number) => void;
  isFirst: boolean;
  isLast: boolean;
  isTouch: boolean;
}

function SortableItem({
  id,
  option,
  index,
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
  isTouch,
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
    zIndex: isDragging ? 50 : undefined,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        "flex items-center gap-3 p-3 rounded-xl border border-slate-200 bg-white transition-shadow",
        isDragging && "shadow-lg border-emerald-300"
      )}
    >
      {/* Rank badge */}
      <span className="flex-shrink-0 w-7 h-7 rounded-full bg-emerald-100 text-emerald-700 text-xs font-bold flex items-center justify-center">
        {index + 1}
      </span>

      {option.icon && (
        <span className="text-2xl leading-none flex-shrink-0" role="img" aria-hidden="true">
          {option.icon}
        </span>
      )}

      <span className="flex-1 text-sm font-medium text-slate-800 text-left">{option.label}</span>

      {/* Drag handle or touch arrows */}
      {isTouch ? (
        <div className="flex flex-col gap-0.5">
          <button
            type="button"
            onClick={() => onMoveUp(index)}
            disabled={isFirst}
            className={cn(
              "p-1 rounded hover:bg-slate-100 transition-colors",
              isFirst && "opacity-30 cursor-not-allowed"
            )}
            aria-label="Move up"
          >
            <ChevronUp className="h-4 w-4 text-slate-500" />
          </button>
          <button
            type="button"
            onClick={() => onMoveDown(index)}
            disabled={isLast}
            className={cn(
              "p-1 rounded hover:bg-slate-100 transition-colors",
              isLast && "opacity-30 cursor-not-allowed"
            )}
            aria-label="Move down"
          >
            <ChevronDown className="h-4 w-4 text-slate-500" />
          </button>
        </div>
      ) : (
        <button
          type="button"
          className="cursor-grab active:cursor-grabbing p-1 text-slate-400 hover:text-slate-600"
          {...attributes}
          {...listeners}
          aria-label="Drag to reorder"
        >
          <GripVertical className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}

interface RankCardProps {
  options: CardOption[];
  orderedIds: string[];
  onReorder: (newOrder: string[]) => void;
}

export function RankCard({ options, orderedIds, onReorder }: RankCardProps) {
  const [isTouch, setIsTouch] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const orderedOptions = orderedIds
    .map((id) => options.find((o) => o.id === id))
    .filter(Boolean) as CardOption[];

  const remaining = options.filter((o) => !orderedIds.includes(o.id));
  const allOptions = [...orderedOptions, ...remaining];

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      const oldIndex = orderedIds.indexOf(active.id as string);
      const newIndex = orderedIds.indexOf(over.id as string);
      if (oldIndex !== -1 && newIndex !== -1) {
        onReorder(arrayMove(orderedIds, oldIndex, newIndex));
      }
    }
  }

  function handleMoveUp(index: number) {
    if (index === 0) return;
    const newOrder = [...orderedIds];
    [newOrder[index - 1], newOrder[index]] = [newOrder[index], newOrder[index - 1]];
    onReorder(newOrder);
  }

  function handleMoveDown(index: number) {
    if (index === orderedIds.length - 1) return;
    const newOrder = [...orderedIds];
    [newOrder[index], newOrder[index + 1]] = [newOrder[index + 1], newOrder[index]];
    onReorder(newOrder);
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-500 font-medium">Kéo để sắp xếp thứ tự ưu tiên</p>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext items={orderedIds} strategy={verticalListSortingStrategy}>
          {orderedOptions.map((opt, i) => (
            <SortableItem
              key={opt.id}
              id={opt.id}
              option={opt}
              index={i}
              onMoveUp={handleMoveUp}
              onMoveDown={handleMoveDown}
              isFirst={i === 0}
              isLast={i === orderedOptions.length - 1}
              isTouch={isTouch}
            />
          ))}
        </SortableContext>
      </DndContext>
    </div>
  );
}
