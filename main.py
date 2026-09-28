import sys
import pygame
from game.game_state import GameStateManager, MenuState

LARGURA_INICIAL = 1024
ALTURA_INICIAL = 720
FPS = 60


def main():
    pygame.init()
    pygame.display.set_caption("Truco Gaudério - O Duelo Cego das Coxilhas")

    # Janela responsiva que suporta redimensionamento e maximização sem tela preta
    tela = pygame.display.set_mode((LARGURA_INICIAL, ALTURA_INICIAL), pygame.RESIZABLE)
    relogio = pygame.time.Clock()

    state_manager = GameStateManager(LARGURA_INICIAL, ALTURA_INICIAL)
    state_manager.mudar_estado(MenuState(state_manager))

    executando = True
    while executando:
        dt = relogio.tick(FPS) / 1000.0  # Delta time em segundos

        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                executando = False
            elif evento.type == pygame.VIDEORESIZE:
                nova_largura = max(800, evento.w)
                nova_altura = max(600, evento.h)
                tela = pygame.display.set_mode(
                    (nova_largura, nova_altura), pygame.RESIZABLE
                )
                state_manager.redimensionar(nova_largura, nova_altura)
            else:
                state_manager.tratar_evento(evento)

        state_manager.atualizar(dt)
        state_manager.desenhar(tela)
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
