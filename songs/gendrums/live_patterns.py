
import subsequence.constants.instruments.gm_drums as gm_drums


DRUMS_CHANNEL = 10

groove = subsequence.Groove.from_agr(r"C:\Users\user\Documents\Ableton\User Library\Grooves\toody terry.agr", grid=0.25)




@composition.pattern(channel=DRUMS_CHANNEL, beats=4, drum_note_map=gm_drums.GM_DRUM_MAP)
def drums (p):
	p.groove(groove, strength=1.0)

	p.bresenham_poly(
        parts={"kick_1": 0.25, "snare_1": 0.125, "hi_hat_closed": 0.5},
        velocity={"kick_1": 100, "snare_1": 90, "hi_hat_closed": 70},
	)
