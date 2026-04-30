/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { Message } from './types';

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

export const sendChatMessage = async (content: string): Promise<string> => {
  await delay(1500); // Simulate AI thinking
  
  const responses = [
    "Tôi hiểu rồi. Dựa trên mục tiêu dinh dưỡng của bạn, tôi khuyên bạn nên bổ sung thêm Protein vào bữa tối nhé.",
    "Bữa trưa hôm nay của bạn có vẻ hơi nhiều Carbs. Bạn có muốn tôi gợi ý một thực đơn cân bằng hơn không?",
    "Đừng quên uống đủ 2.5L nước mỗi ngày để hỗ trợ quá trình trao đổi chất nhé!",
    "Bài tập Push Day hôm nay rất tuyệt! Bạn nên ăn một bữa nhẹ sau tập trong vòng 30 phút.",
    "Tôi có thể giúp gì thêm về thực đơn tuần tới của bạn không?"
  ];
  
  return responses[Math.floor(Math.random() * responses.length)];
};
