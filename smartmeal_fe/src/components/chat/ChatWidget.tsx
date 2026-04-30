/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from 'react';
import { AnimatePresence } from 'motion/react';
import { ChatBubble } from './ChatBubble';
import { ChatPanel } from './ChatPanel';
import { Message } from './types';
import { sendChatMessage } from './chatService';

export function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: 'Chào Nguyễn! Tôi là SmartMeal AI. Tôi có thể hỗ trợ bạn tính toán macro, gợi ý thực đơn hoặc lịch tập gym hôm nay. Bạn cần giúp gì không?',
      timestamp: new Date()
    }
  ]);
  const [isTyping, setIsTyping] = useState(false);

  const handleSendMessage = async (content: string) => {
    // Add user message
    const userMsg: Message = {
      id: Math.random().toString(36).substr(2, 9),
      role: 'user',
      content,
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, userMsg]);
    setIsTyping(true);

    try {
      const response = await sendChatMessage(content);
      const aiMsg: Message = {
        id: Math.random().toString(36).substr(2, 9),
        role: 'assistant',
        content: response,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, aiMsg]);
    } catch (error) {
      console.error("AI Chat Error:", error);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="fixed bottom-0 right-0 z-[100]">
      <AnimatePresence>
        {isOpen && (
          <ChatPanel 
            messages={messages} 
            isTyping={isTyping} 
            onSendMessage={handleSendMessage}
            onMinimize={() => setIsOpen(false)}
          />
        )}
      </AnimatePresence>
      <ChatBubble isOpen={isOpen} onClick={() => setIsOpen(!isOpen)} />
    </div>
  );
}
