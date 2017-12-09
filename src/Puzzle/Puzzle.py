from Puzzle.Distance import diff_match_edges, diff_match_edges2
from Puzzle.PuzzlePiece import *

from Puzzle.Extractor import Extractor
from Puzzle.Mover import *
from Img.filters import load_signatures
from cv2 import cv2

from Puzzle.Enums import *
import sys
import scipy



class Puzzle():
    def __init__(self, path, pixmapWidget=None):
        self.extract = Extractor(path, pixmapWidget)
        self.pieces_ = self.extract.extract()
        print('>>> START solving puzzle')

        border_pieces = []
        non_border_pieces = []

        # Separate border pieces from the other
        for piece in self.pieces_:
            if piece.number_of_border():
                border_pieces.append(piece)
            else:
                non_border_pieces.append(piece)

        # Start by a corner piece
        for piece in border_pieces:
            if piece.number_of_border() > 1:
                connected_pieces = [piece]
                border_pieces.remove(piece)
                break

        print("Number of border pieces: ", len(border_pieces) + 1)
        left_pieces = border_pieces

        #connected_pieces = [self.pieces_[0]]
        #left_pieces = self.pieces_[1:]
        #self.solve(connected_pieces, left_pieces)
        self.solve(connected_pieces, left_pieces, border=True)
        # self.solve(self.pieces_, non_border_pieces)
        print('>>> SAVING result...')
        self.translate_puzzle()
        self.export_pieces("/tmp/stick.png", "/tmp/colored.png")


        # Two sets of pieces: Already connected ones and pieces remaining to connect to the others
        # The first piece has an orientation like that:
        #         N          edges:    0
        #      W     E              3     1
        #         S                    2
        #
        # Pieces are placed on a grid like that (X is the first piece at position (0, 0)):
        # +--+--+--+
        # |  |  |  |
        # +--+--+--+
        # |  | X|  |
        # +--+--+--+
        # |  |  |  |
        # +--+--+--+
        #
        # Then if we test the NORTH edge:
        # +--+--+--+
        # |  | X|  |
        # +--+--+--+
        # |  | X|  |
        # +--+--+--+
        # |  |  |  |
        # +--+--+--+
        # Etc until the puzzle is complete i.e. there is no pieces left on left_pieces.

    def solve(self, connected_pieces, left_pieces, border=False):
        angles = filter(lambda x: x.type == TypePiece.ANGLE, left_pieces)
        borders = filter(lambda x: x.type == TypePiece.BORDER, left_pieces)
        centers = filter(lambda x: x.type == TypePiece.CENTER, left_pieces)
        connected_directions = [((0, 0), connected_pieces[0])] # ((x, y), p), x & y relative to the first piece, init with 1st piece

        diff = {}


        # while there are still pieces to connect...
        while len(left_pieces) > 0:
            print("<--- New match --->")
            to_break = False
            for p in connected_pieces:
                for e in p.edges_:
                    # for each connected_pieces, for each edges, if the edges is not connected we need
                    # to find the correct piece/edge to connect the piece to
                    if e.connected:
                        continue

                    # Stick best get a list of pieces to test and return the index of the best match (piece/edge)
                    best_p, best_e = self.stick_best(p, e, left_pieces, border)

                    self.update_direction(e, best_p, best_e)
                    self.connect_piece(connected_directions, p, e.direction, best_p)

                    # We are adding pieces to connected_pieces while looping into it so I break
                    connected_pieces.append(best_p)
                    del left_pieces[left_pieces.index(best_p)]
                    to_break = True
                    break
                if to_break:
                    break
            self.export_pieces("/tmp/stick" + str(len(left_pieces)) + ".png", "/tmp/colored" + str(len(left_pieces)) + ".png")
        self.pieces_ = connected_pieces


    def compute_diffs(self, pieces):
        pass


    def update_direction(self, e, best_p, best_e):
        opp = get_opposite_direction(e.direction)
        step = step_direction(opp, best_e.direction)
        for edge in best_p.edges_:
            edge.direction = rotate_direction(edge.direction, step)

    def connect_piece(self, connected_directions, curr_p, dir, best_p):
        def add_tuple(a, b):
            return a[0] + b[0], a[1] + b[1]
        def equals_tuple(a, b):
            return a[0] == b[0] and a[1] == b[1]
        # Then we need to search the other pieces already in the puzzle that are going to be also connected:
        # +--+--+--+
        # |  | X| O|
        # +--+--+--+
        # |  | X| X|
        # +--+--+--+
        # |  |  |  |
        # +--+--+--+
        #
        # For example if I am going to put a piece at the marker 'O' only one edge will be connected to the piece
        # therefore we need to search the adjacent pieces and connect them properly

        old_coord = list(filter(lambda x: x[1] == curr_p, connected_directions))[0][0]
        new_coord = add_tuple(old_coord, dir.value)

        for (coord, p) in connected_directions:
            for d in directions:
                if equals_tuple(coord, add_tuple(new_coord, d.value)):
                    for edge in best_p.edges_:
                        if edge.direction == d:
                            edge.connected = True
                            break
                    for edge in p.edges_:
                        if edge.direction == get_opposite_direction(d):
                            edge.connected = True
                            break
        connected_directions.append((new_coord, best_p))
        print('matched:', list([e[0] for e in connected_directions]))




    def stick_best(self, cur_piece, cur_edge, pieces, border=False):
        if cur_edge.connected:
            return

        edges_to_test = []
        for piece in pieces:
            if piece != cur_piece:
                for edge in piece.edges_:
                    # if border and piece.nBorders_ < 2 and piece.borders_[(index_edge + 2) % 4]: # FIXME ?
                    #     continue
                    if not edge.connected:
                        edges_to_test.append((piece, edge))

        diff = []
        for piece, edge in edges_to_test:
            # Stick pieces to test distance
            for e in piece.edges_:
                e.backup_shape()
            stick_pieces(cur_piece, cur_edge, piece, edge)
            for e in piece.edges_:
                e.restore_backup_shape()
            diff.append(1 * diff_match_edges(edge.shape, cur_edge.shape))


        # Stick the best piece found
        best_p, best_e = edges_to_test[np.argmin(diff)]
        stick_pieces(cur_piece, cur_edge, best_p, best_e, final_stick=True)

        return best_p, best_e

    def translate_puzzle(self):
        # Translate all pieces to the top left corner to be sure the puzzle is in the image
        minX = sys.maxsize
        minY = sys.maxsize
        for p in self.pieces_:
            for e in p.edges_:
                for pixel in e.shape:
                    if pixel[0] < minX:
                        minX = pixel[0]
                    if pixel[1] < minY:
                        minY = pixel[1]

        for p in self.pieces_:
            for e in p.edges_:
                for ip, _ in enumerate(e.shape):
                    e.shape[ip] += (-minX, -minY)

        for piece in self.pieces_:
            for p in piece.img_piece_:
                p.translate(minX, minY)

    def export_pieces(self, path_contour, path_colored):
        minX, minY = float('inf'), float('inf')
        maxX, maxY = -float('inf'), -float('inf')
        for piece in self.pieces_:
            for p in piece.img_piece_:
                x, y = p.pos
                minX, minY = min(minX, x), min(minY, y)
                maxX, maxY = max(maxX, x), max(maxY, y)

        colored_img = np.zeros((maxX - minX, maxY - minY, 3))

        border_img = np.zeros((maxX - minX, maxY - minY, 1))

        for piece in self.pieces_:
            for p in piece.img_piece_:
                p.apply(colored_img, dx=-minX, dy=-minY)
            # Contours
            for e in piece.edges_:
                for y, x in e.shape:
                    y, x = y - minY, x - minX
                    if 0 <= y < border_img.shape[1] and 0 <= x < border_img.shape[0]:
                        border_img[x, y] = 255

        # cv2.circle(tests_img, tuple((int(puzzle_pieces[1].edges_[0][0][0]), int(centerY))), 10, 255, -1)
        cv2.imwrite(path_contour, border_img)
        cv2.imwrite(path_colored, colored_img)
