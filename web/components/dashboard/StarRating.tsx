
import React from 'react'
import { Star } from 'lucide-react'

interface StarRatingProps {
    score: number; // 1-5
    size?: number;
}

export default function StarRating({ score, size = 14 }: StarRatingProps) {
    // Clamp score between 0 and 5
    const validScore = Math.max(0, Math.min(5, score));
    const stars = [1, 2, 3, 4, 5];

    return (
        <div className="flex gap-0.5">
            {stars.map((i) => (
                <Star
                    key={i}
                    size={size}
                    className={`${i <= validScore
                            ? 'text-amber-400 fill-amber-400'
                            : 'text-gray-200 fill-gray-100'
                        }`}
                />
            ))}
        </div>
    )
}
