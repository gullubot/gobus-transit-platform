package com.transitplatform.passenger.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Fill
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.transitplatform.passenger.ui.theme.EcoGreen
import com.transitplatform.passenger.ui.theme.GoBusBlue

/**
 * Custom vector icons faithful to Reference 2 icon specifications.
 */

@Composable
fun EcoLeafIcon(
    modifier: Modifier = Modifier.size(24.dp),
    tint: Color = EcoGreen
) {
    Canvas(modifier = modifier) {
        val w = size.width
        val h = size.height
        val scaleX = w / 24f
        val scaleY = h / 24f

        // Right (larger) leaf
        val rightLeaf = Path().apply {
            moveTo(11f * scaleX, 15f * scaleY)
            cubicTo(
                11f * scaleX, 10f * scaleY,
                15f * scaleX, 4f * scaleY,
                22f * scaleX, 3f * scaleY
            )
            cubicTo(
                21f * scaleX, 10f * scaleY,
                18f * scaleX, 15f * scaleY,
                12.5f * scaleX, 16f * scaleY
            )
            close()
        }
        drawPath(path = rightLeaf, color = tint, style = Fill)

        // Left (smaller) leaf
        val leftLeaf = Path().apply {
            moveTo(11f * scaleX, 16f * scaleY)
            cubicTo(
                8f * scaleX, 13f * scaleY,
                3f * scaleX, 10f * scaleY,
                2f * scaleX, 7f * scaleY
            )
            cubicTo(
                4f * scaleX, 13f * scaleY,
                7f * scaleX, 16.5f * scaleY,
                10.5f * scaleX, 17f * scaleY
            )
            close()
        }
        drawPath(path = leftLeaf, color = tint, style = Fill)

        // Stem
        val stem = Path().apply {
            moveTo(11f * scaleX, 15f * scaleY)
            quadraticTo(
                11f * scaleX, 19f * scaleY,
                9f * scaleX, 22f * scaleY
            )
        }
        drawPath(
            path = stem,
            color = tint,
            style = Stroke(width = 2f * scaleX, cap = StrokeCap.Round)
        )
    }
}

@Composable
fun DepotIcon(
    modifier: Modifier = Modifier.size(24.dp),
    tint: Color = GoBusBlue
) {
    Canvas(modifier = modifier) {
        val w = size.width
        val h = size.height
        val sx = w / 24f
        val sy = h / 24f

        // Roof / Triangular pediment
        val pediment = Path().apply {
            moveTo(12f * sx, 3f * sy)
            lineTo(22f * sx, 8.5f * sy)
            lineTo(2f * sx, 8.5f * sy)
            close()
        }
        drawPath(path = pediment, color = tint, style = Fill)

        // Architrave / Lintel below roof
        drawRect(
            color = tint,
            topLeft = Offset(3f * sx, 8.5f * sy),
            size = Size(18f * sx, 1.8f * sy)
        )

        // 4 Columns / Pillars
        val pillarWidth = 2.4f * sx
        val pillarHeight = 7.5f * sy
        val pillarY = 11f * sy
        val pillarXs = listOf(4.5f * sx, 9f * sx, 13.5f * sx, 18f * sx)
        for (x in pillarXs) {
            drawRect(
                color = tint,
                topLeft = Offset(x - pillarWidth / 2f, pillarY),
                size = Size(pillarWidth, pillarHeight)
            )
        }

        // Base plinth / foundation
        drawRect(
            color = tint,
            topLeft = Offset(2f * sx, 19f * sy),
            size = Size(20f * sx, 2.5f * sy)
        )
    }
}

@Composable
fun SwapArrowsIcon(
    modifier: Modifier = Modifier.size(24.dp),
    tint: Color = GoBusBlue
) {
    Canvas(modifier = modifier) {
        val w = size.width
        val h = size.height
        val sx = w / 24f
        val sy = h / 24f
        val strokeWidth = 2.4f * sx

        // Left arrow pointing UP
        val leftX = 8.5f * sx
        val upShaft = Path().apply {
            moveTo(leftX, 18.5f * sy)
            lineTo(leftX, 6f * sy)
        }
        drawPath(
            path = upShaft,
            color = tint,
            style = Stroke(width = strokeWidth, cap = StrokeCap.Round)
        )

        val upHead = Path().apply {
            moveTo(leftX - 3.5f * sx, 9.5f * sy)
            lineTo(leftX, 5.5f * sy)
            lineTo(leftX + 3.5f * sx, 9.5f * sy)
        }
        drawPath(
            path = upHead,
            color = tint,
            style = Stroke(width = strokeWidth, cap = StrokeCap.Round, join = StrokeJoin.Round)
        )

        // Right arrow pointing DOWN
        val rightX = 15.5f * sx
        val downShaft = Path().apply {
            moveTo(rightX, 5.5f * sy)
            lineTo(rightX, 18f * sy)
        }
        drawPath(
            path = downShaft,
            color = tint,
            style = Stroke(width = strokeWidth, cap = StrokeCap.Round)
        )

        val downHead = Path().apply {
            moveTo(rightX - 3.5f * sx, 14.5f * sy)
            lineTo(rightX, 18.5f * sy)
            lineTo(rightX + 3.5f * sx, 14.5f * sy)
        }
        drawPath(
            path = downHead,
            color = tint,
            style = Stroke(width = strokeWidth, cap = StrokeCap.Round, join = StrokeJoin.Round)
        )
    }
}
